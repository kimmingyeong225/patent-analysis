"""
/search 엔드포인트 영구 캐시용 DB 접근 계층.

- get_cached_search: 동일 query의 SearchResult + 관련 테이블을 조인하여 dict 복원
- save_search_results: KIPRIS 결과를 Patent/Citation/LegalStatus/Classification/SearchResult에 저장
- db_row_to_search_result_item: ORM Patent → SearchResultItem dict 변환 헬퍼

필터(year/status/max_results)는 캐시된 '원본'에 후처리로 적용한다. 그래야 같은 쿼리에
다른 필터 조합이 와도 캐시 적중률이 유지된다.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session, joinedload

import models
import schemas
from kipris import STALE_CLAIMS_PLACEHOLDER

logger = logging.getLogger(__name__)

# stale 감지 시 쓰는 prefix — 전체 문자열을 그대로 비교하면 공백/버전 차이에 취약하므로
# 앞쪽 일부만 비교해 안전 마진을 확보한다.
_STALE_PREFIX = STALE_CLAIMS_PLACEHOLDER[:20]


def _is_stale_items(items: list, check_limit: int) -> bool:
    """캐시에서 복원된 items 중 상위 check_limit 건에 한해 placeholder 검사.

    판정 규칙 (items[:check_limit] 범위 내):
      - claims가 None/빈 리스트 → stale (상세조회 미보강 상태)
      - claims[0]이 STALE_CLAIMS_PLACEHOLDER prefix로 시작 → stale
      하나라도 걸리면 전체 query를 재조회.

    스코프 제한 근거 (하이브리드 저장 전략):
      - /search는 상위 max_results 건만 enrich하고 나머지는 placeholder로 저장한다.
      - 따라서 rank > max_results 건의 placeholder는 "캐시 정상 상태"이며
        stale 판정 근거가 아니다. 이 범위까지 검사하면 매번 stale 오탐 → 무한 재조회.

    빈 rows로 인한 "캐시 miss"(get_cached_search가 None 반환)와는
    의미가 다르다 — 빈 캐시는 애초에 이 함수에 들어오지 않는다.
    """
    if check_limit <= 0:
        return False
    for it in items[:check_limit]:
        pub = it.get("공개등록공보") or {}
        claims = pub.get("claims")
        if not claims:
            return True
        first = claims[0] if isinstance(claims[0], str) else ""
        if first.startswith(_STALE_PREFIX):
            return True
    return False


def db_row_to_search_result_item(patent: models.Patent) -> dict:
    """Patent ORM 객체(관련 Citation/LegalStatus/Classification 포함)를
    SearchResultItem 스키마 형태의 dict로 변환.

    rank / similarity_score는 SearchResult 테이블에서 와야 하므로 placeholder(0)로 채우고,
    호출자가 SearchResult 행의 실제 값으로 덮어쓴다.
    """
    citation = patent.citation
    legal = patent.legal_status
    classifications = patent.classifications or []

    ipc = [
        {"code": c.code or "", "desc": c.desc or ""}
        for c in classifications if c.code_type == "ipc"
    ]
    cpc = [
        {"code": c.code or "", "desc": c.desc or ""}
        for c in classifications if c.code_type == "cpc"
    ]

    return {
        "rank": 0,
        "similarity_score": 0.0,
        "공개등록공보": {
            "patent_id": patent.patent_id,
            "application_number": patent.application_number or "",
            "title": patent.title or "",
            "applicant": patent.applicant or "",
            "inventor": patent.inventor or "",
            "application_date": patent.application_date or "",
            "publication_date": patent.publication_date,
            "registration_date": patent.registration_date,
            "abstract": patent.abstract or "요약이 제공되지 않았습니다.",
            "claims": patent.claims or [],
            "doc_type": patent.doc_type or "",
        },
        "인용문헌": {
            "cited_by_count": citation.cited_by_count if citation else 0,
            "citing_count": citation.citing_count if citation else 0,
            "cited_patents": (
                citation.cited_patents if citation and citation.cited_patents else []
            ),
        },
        "법적상태": {
            "status": legal.status if legal else "",
            "status_code": legal.status_code if legal else "",
            "last_event": legal.last_event if legal else "",
            "last_event_date": legal.last_event_date if legal else None,
            "is_alive": bool(legal.is_alive) if legal else False,
        },
        "분류코드": {
            "ipc": ipc,
            "cpc": cpc,
        },
    }


def _apply_cache_filters(results: list, request: schemas.SearchRequest) -> list:
    """캐시된 dict 리스트에 year/status 필터를 적용. (main._apply_filters와 동일 규칙)"""
    filtered = results

    if request.year_from or request.year_to:
        def in_year_range(p):
            date = p.get("공개등록공보", {}).get("application_date", "") or ""
            if len(date) < 4:
                return False
            try:
                year = int(date[:4])
            except ValueError:
                return False
            if request.year_from and year < request.year_from:
                return False
            if request.year_to and year > request.year_to:
                return False
            return True
        filtered = [p for p in filtered if in_year_range(p)]

    if request.status:
        filtered = [
            p for p in filtered
            if p.get("법적상태", {}).get("status", "") == request.status
        ]

    return filtered


def get_cached_search(
    db: Session, query: str, request: schemas.SearchRequest
) -> Optional[list]:
    """동일 query의 캐시된 검색 결과를 조회.
    - 있으면 필터 + max_results 적용 후 rank 재부여한 dict 리스트 반환
    - 없으면 None
    """
    rows = (
        db.query(models.SearchResult)
        .options(
            joinedload(models.SearchResult.patent).joinedload(models.Patent.citation),
            joinedload(models.SearchResult.patent).joinedload(models.Patent.legal_status),
            joinedload(models.SearchResult.patent).joinedload(models.Patent.classifications),
        )
        .filter(models.SearchResult.query == query)
        .order_by(models.SearchResult.rank.asc())
        .all()
    )
    if not rows:
        return None

    items = []
    for row in rows:
        if row.patent is None:
            continue
        item = db_row_to_search_result_item(row.patent)
        item["rank"] = row.rank if row.rank is not None else 0
        item["similarity_score"] = float(row.similarity_score or 0.0)
        items.append(item)

    # stale 감지 — 상위 max_results 건에서만 placeholder/빈 claims 검사.
    # rank 하위 건은 enrich 대상이 아니므로 placeholder가 정상 (하이브리드 저장 전략).
    # 빈 rows로 인한 "캐시 miss"와는 구분되는 경로 (이 지점에 도달했다는 건 rows는 존재).
    if _is_stale_items(items, request.max_results):
        logger.info(
            "stale cache detected for query %s → None 반환으로 재조회 유도",
            query,
        )
        # 해당 query의 SearchResult 매핑만 회수 (Patent/Citation/LegalStatus는 공유 가능성 보존).
        # 재조회 후 save_search_results의 Patent upsert가 claims를 갱신함.
        try:
            db.query(models.SearchResult).filter(
                models.SearchResult.query == query
            ).delete(synchronize_session=False)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("stale SearchResult 정리 실패(무시 가능): %s", e)
        return None

    items = _apply_cache_filters(items, request)
    items = items[: request.max_results]
    for i, p in enumerate(items):
        p["rank"] = i + 1
    return items


def save_search_results(db: Session, query: str, results: list) -> None:
    """KIPRIS 결과(FAISS 점수·rank 포함)를 DB에 저장.

    - Patent: patent_id 중복이면 skip
    - Citation / LegalStatus: 1:1, 있으면 update / 없으면 insert
    - Classification: 1:N, 해당 patent_id 전부 삭제 후 재삽입
    - SearchResult: 해당 query 전부 삭제 후 재삽입
    전체를 하나의 트랜잭션으로 처리하고 실패 시 rollback.
    """
    try:
        # 동일 query의 기존 매핑 제거 (원본 테이블은 건드리지 않음)
        db.query(models.SearchResult).filter(
            models.SearchResult.query == query
        ).delete(synchronize_session=False)

        for idx, item in enumerate(results):
            pub = item.get("공개등록공보", {}) or {}
            cit = item.get("인용문헌", {}) or {}
            legal = item.get("법적상태", {}) or {}
            codes = item.get("분류코드", {}) or {}

            patent_id = pub.get("patent_id")
            if not patent_id:
                continue

            # Patent: upsert (Citation/LegalStatus와 동일 패턴)
            # - 기존 행이 있어도 상세조회로 보강된 claims/abstract를 반영할 수 있도록 update
            # - 단, 상세조회가 실패해 placeholder가 섞인 경우를 구분하기 위해 호출측이
            #   이미 _enrich_top_patents_with_detail을 돌린 뒤 저장하는 것을 전제로 함
            existing = db.query(models.Patent).filter(
                models.Patent.patent_id == patent_id
            ).first()
            if existing:
                existing.application_number = pub.get("application_number")
                existing.title = pub.get("title")
                existing.applicant = pub.get("applicant")
                existing.inventor = pub.get("inventor")
                existing.application_date = pub.get("application_date")
                existing.publication_date = pub.get("publication_date")
                existing.registration_date = pub.get("registration_date")
                existing.abstract = pub.get("abstract")
                existing.claims = pub.get("claims") or []
                existing.doc_type = pub.get("doc_type")
            else:
                db.add(models.Patent(
                    patent_id=patent_id,
                    application_number=pub.get("application_number"),
                    title=pub.get("title"),
                    applicant=pub.get("applicant"),
                    inventor=pub.get("inventor"),
                    application_date=pub.get("application_date"),
                    publication_date=pub.get("publication_date"),
                    registration_date=pub.get("registration_date"),
                    abstract=pub.get("abstract"),
                    claims=pub.get("claims") or [],
                    doc_type=pub.get("doc_type"),
                ))

            # Citation upsert (1:1)
            cit_row = db.query(models.Citation).filter(
                models.Citation.patent_id == patent_id
            ).first()
            if cit_row:
                cit_row.cited_by_count = cit.get("cited_by_count", 0) or 0
                cit_row.citing_count = cit.get("citing_count", 0) or 0
                cit_row.cited_patents = cit.get("cited_patents") or []
            else:
                db.add(models.Citation(
                    patent_id=patent_id,
                    cited_by_count=cit.get("cited_by_count", 0) or 0,
                    citing_count=cit.get("citing_count", 0) or 0,
                    cited_patents=cit.get("cited_patents") or [],
                ))

            # LegalStatus upsert (1:1)
            legal_row = db.query(models.LegalStatus).filter(
                models.LegalStatus.patent_id == patent_id
            ).first()
            if legal_row:
                legal_row.status = legal.get("status", "") or ""
                legal_row.status_code = legal.get("status_code", "") or ""
                legal_row.last_event = legal.get("last_event", "") or ""
                legal_row.last_event_date = legal.get("last_event_date")
                legal_row.is_alive = bool(legal.get("is_alive", False))
            else:
                db.add(models.LegalStatus(
                    patent_id=patent_id,
                    status=legal.get("status", "") or "",
                    status_code=legal.get("status_code", "") or "",
                    last_event=legal.get("last_event", "") or "",
                    last_event_date=legal.get("last_event_date"),
                    is_alive=bool(legal.get("is_alive", False)),
                ))

            # Classification: 기존 전부 삭제 후 재삽입 (ipc/cpc 각각)
            db.query(models.Classification).filter(
                models.Classification.patent_id == patent_id
            ).delete(synchronize_session=False)
            for code_type in ("ipc", "cpc"):
                for c in codes.get(code_type, []) or []:
                    db.add(models.Classification(
                        patent_id=patent_id,
                        code_type=code_type,
                        code=(c or {}).get("code", "") or "",
                        desc=(c or {}).get("desc", "") or "",
                    ))

            # SearchResult insert (rank 누락 시 enum index + 1로 fallback)
            rank_val = item.get("rank")
            if rank_val is None:
                rank_val = idx + 1
            db.add(models.SearchResult(
                query=query,
                patent_id=patent_id,
                rank=int(rank_val),
                similarity_score=float(item.get("similarity_score") or 0.0),
            ))

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("save_search_results 실패, rollback: %s", e)
        raise

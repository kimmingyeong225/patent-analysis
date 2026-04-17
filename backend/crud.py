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

logger = logging.getLogger(__name__)


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

            # Patent: 중복 skip
            existing = db.query(models.Patent).filter(
                models.Patent.patent_id == patent_id
            ).first()
            if not existing:
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

import logging
import time

import requests
import xmltodict
from config import KIPRIS_API_KEY

logger = logging.getLogger(__name__)

# KIPRIS 특허/실용신안 무료 검색 서비스 URL (freeSearch / trend 용)
KIPRIS_SEARCH_URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"

# 서지상세조회 — 베이스 경로와 API 키 필드명이 freeSearch와 다름
# - 베이스: /kipo-api/kipi/... (freeSearch: /openapi/rest/...)
# - 키필드: ServiceKey (freeSearch: accessKey)
KIPRIS_DETAIL_URL = (
    "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/"
    "getBibliographyDetailInfoSearch"
)

# freeSearch 단계에서만 삽입되는 청구항 placeholder.
# crud.get_cached_search가 이 문자열로 stale cache를 감지해 자동 재조회를 트리거.
STALE_CLAIMS_PLACEHOLDER = "청구범위 정보는 상세조회 API에서 확인 가능합니다."


# 공통 헬퍼 ─────────────────────────────────────────────

def _ensure_list(value) -> list:
    """xmltodict는 반복 태그가 1건이면 dict로, 없으면 None을 반환.
    이를 항상 리스트로 정규화해 downstream 루프를 단순화한다.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_date(s) -> str:
    """상세조회는 'YYYY.MM.DD', freeSearch는 'YYYYMMDD' 포맷.
    DB/필터 일관성을 위해 점·하이픈·공백을 제거하여 'YYYYMMDD'로 통일한다.
    None/빈 문자열은 ''로.
    """
    if not s:
        return ""
    return str(s).replace(".", "").replace("-", "").strip()


def _kipris_request(
    url: str,
    params: dict,
    timeout: int = 15,
    max_attempts: int = 3,
) -> requests.Response:
    """KIPRIS GET 요청 (URL 파라미터화). 타임아웃/연결오류/5xx 에 한해 지수 백오프 재시도.
    4xx는 재시도 없이 즉시 raise (요청 자체가 잘못된 경우).
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if 500 <= resp.status_code < 600:
                # 5xx → 재시도 경로
                if attempt == max_attempts:
                    resp.raise_for_status()
                backoff = min(2 ** (attempt - 1), 4)
                logger.warning(
                    "KIPRIS %d 응답, %ds 후 재시도 %d/%d",
                    resp.status_code, backoff, attempt, max_attempts,
                )
                time.sleep(backoff)
                continue
            resp.raise_for_status()  # 4xx는 즉시 raise
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if attempt == max_attempts:
                raise
            backoff = min(2 ** (attempt - 1), 4)
            logger.warning(
                "KIPRIS 네트워크 오류, %ds 후 재시도 %d/%d: %s",
                backoff, attempt, max_attempts, e,
            )
            time.sleep(backoff)
    # 논리적으로 도달 불가 — 방어적 raise
    raise last_exc or RuntimeError("KIPRIS 재시도 소진")


def _kipris_get(params: dict, timeout: int = 15, max_attempts: int = 3) -> requests.Response:
    """freeSearch 전용 요청. 기존 호출부 호환을 위해 시그니처 유지."""
    return _kipris_request(KIPRIS_SEARCH_URL, params, timeout, max_attempts)

def fetch_trend_data_from_kipris(query: str, max_count: int = 500) -> dict:
    """
    트렌드 집계 전용. KIPRIS API를 페이지네이션하여 최대 max_count건을 수집하고
    연도별 출원 건수를 반환합니다. (API 1회 최대 100건이므로 여러 번 호출)
    반환값: { "trend_data": [...], "is_truncated": bool }
      - is_truncated=True  → max_count 한계에 도달 (실제 건수는 더 많을 수 있음)
      - is_truncated=False → 전체 결과를 모두 수집함
    """
    PAGE_SIZE = 100
    year_counts: dict[str, int] = {}
    fetched = 0

    try:
        for page in range(max_count // PAGE_SIZE):
            params = {
                "word": query,
                "accessKey": KIPRIS_API_KEY,
                "docsStart": str(page * PAGE_SIZE + 1),
                "docsCount": str(PAGE_SIZE),
            }
            try:
                response = _kipris_get(params, timeout=15)
            except requests.RequestException as e:
                logger.warning("Trend KIPRIS 페이지 %d 실패, 중단: %s", page, e)
                break

            xml_dict = xmltodict.parse(response.text)
            items = (
                xml_dict.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("PatentUtilityInfo", [])
            )
            if isinstance(items, dict):
                items = [items]
            if not items:
                break  # 더 이상 결과 없음

            for item in items:
                date = item.get("ApplicationDate", "") or ""
                if len(date) >= 4:
                    year = date[:4]
                    if year.isdigit():
                        year_counts[year] = year_counts.get(year, 0) + 1

            fetched += len(items)
            if len(items) < PAGE_SIZE:
                break  # 마지막 페이지 도달

        trend_data = [{"year": y, "count": c} for y, c in sorted(year_counts.items())]
        return {"trend_data": trend_data, "is_truncated": fetched >= max_count}

    except Exception as e:
        logger.error("Trend KIPRIS fetch error: %s", e)
        return {"trend_data": [], "is_truncated": False}


def fetch_patent_data_from_kipris(query: str, docs_count: int = 30):
    """
    KIPRIS API를 호출하여 특허 검색 결과를 XML에서 JSON(dict)으로 파싱.
    docs_count: KIPRIS에서 가져올 최대 건수 (필터링 전 모수, 기본 30건)
    """
    params = {
        "word": query,
        "accessKey": KIPRIS_API_KEY,
        "docsStart": "1",
        "docsCount": str(docs_count),
    }

    try:
        response = _kipris_get(params, timeout=15)
        xml_dict = xmltodict.parse(response.text)
        return parse_kipris_dict_to_json(xml_dict)
    except Exception as e:
        logger.error("KIPRIS API Error: %s", e)
        # 오류 발생 시 빈 리스트 반환 (호출자가 mock 폴백)
        return []

def parse_kipris_dict_to_json(xml_dict: dict):
    """
    xmltodict로 변환된 KIPRIS 응답 데이터를 
    UI/LLM 팀과 합의한 스키마(SearchResultItem) 형태에 맞게 가공합니다.
    사용자 제공 매핑 가이드를 반영함.
    """
    results = []
    
    try:
        # KIPRIS API의 결과 아이템 목록 경로 (API 스펙에 따라 달라질 수 있음)
        items = xml_dict.get('response', {}).get('body', {}).get('items', {}).get('PatentUtilityInfo', [])
        
        # 결과가 하나일 경우 리스트가 아니라 dict로 반환되므로 리스트로 변환
        if isinstance(items, dict):
            items = [items]
            
        for idx, item in enumerate(items):
            # KIPRIS API (FreeSearch) 의 응답 태그 매핑 반영
            # 발명의명칭 -> title
            # 출원인명 -> applicant
            # 발명자명 -> inventor
            # 출원번호 -> application_number
            # 공개일자 -> publication_date
            # 등록일자 -> registration_date
            # 초록청구범위 -> abstract / claims
            # IPC코드 -> ipc[].code
            # 특허실용행정처분 -> 법적상태.status
            
            patent_id = item.get('OpeningNumber', '') or item.get('RegistrationNumber', '') or f"UNKNOWN-{idx}"
            ipc_codes = (item.get('InternationalpatentclassificationNumber') or '').split('|')
            ipc_list = [{"code": code.strip(), "desc": ""} for code in ipc_codes if code.strip()]

            mapped_item = {
                "rank": idx + 1,
                # FAISS가 main._apply_faiss_scores에서 실제 코사인 유사도로 덮어씀.
                # FAISS 실패 시에는 0.0이 남아 UI에서 "점수 없음"으로 표시된다.
                # (이전: round(0.95 - idx*0.05, 2) → KIPRIS 랭크 기반 가짜 점수)
                "similarity_score": 0.0,
                "공개등록공보": {
                    "patent_id": patent_id,
                    "application_number": item.get('ApplicationNumber', patent_id),
                    "title": item.get('InventionName', '제목 없음'),
                    "applicant": item.get('Applicant', '출원인 정보 없음'),
                    "inventor": item.get('Inventor', '발명자 정보 없음'),
                    "application_date": _normalize_date(item.get('ApplicationDate', '')),
                    "publication_date": _normalize_date(item.get('OpeningDate', '')),
                    "registration_date": _normalize_date(item.get('RegistrationDate', '')) or None,
                    "abstract": item.get('Abstract', '요약이 제공되지 않았습니다.'),
                    # 상세조회 병렬 호출 이전 단계의 placeholder. main.py /search에서 덮어씀.
                    # crud.get_cached_search가 이 문자열로 stale 캐시를 감지함.
                    "claims": [STALE_CLAIMS_PLACEHOLDER],
                    "doc_type": item.get('RegistrationStatus', '공개')
                },
                "인용문헌": {
                    "cited_by_count": 0,
                    "citing_count": 0,
                    "cited_patents": []
                },
                "법적상태": {
                    "status": item.get('RegistrationStatus', '상태 알 수 없음'),
                    "status_code": "R0000",
                    "last_event": item.get('RegistrationStatus', ''),
                    "last_event_date": item.get('OpeningDate', ''),
                    "is_alive": True if item.get('RegistrationStatus') in ['등록', '공개'] else False
                },
                "분류코드": {
                    "ipc": ipc_list,
                    "cpc": []
                }
            }
            results.append(mapped_item)

    except Exception as e:
        logger.error("Parsing Error: %s", e)

    return results


# 서지상세조회 ─────────────────────────────────────────────
#
# ⚠️ 비용/쿼터 메모:
#   - /search 1회당 KIPRIS 호출 수: 기존 1회 → 1 + max_results 회 (기본 1+5=6회)
#   - 무료 월 1000회 한도 기준 하루 약 30회 신규 검색 가능 (DB 캐시 히트는 호출 없음)
#   - 프로덕션 시 상세조회를 비동기 큐/스케줄러로 분리 검토
#
# 응답 파싱 경로 (프로브로 확인됨 — 2026-04-17 기준):
#   response.body.item.claimInfoArray.claimInfo[*].claim
#   response.body.item.abstractInfoArray.abstractInfo.astrtCont
#   response.body.item.priorArtDocumentsInfoArray.priorArtDocumentsInfo[*].documentsNumber
#   response.body.item.legalStatusInfoArray.legalStatusInfo[*]

def _kipris_get_detail(application_number: str, timeout: int = 20) -> requests.Response:
    """서지상세조회 전용 GET. 재시도/백오프는 freeSearch와 동일 규칙 사용."""
    params = {
        "applicationNumber": application_number,
        "ServiceKey": KIPRIS_API_KEY,  # 주의: 대문자 S (freeSearch의 accessKey와 다름)
    }
    return _kipris_request(KIPRIS_DETAIL_URL, params, timeout=timeout)


def fetch_patent_detail(application_number: str) -> dict | None:
    """출원번호 1건의 서지상세 정보를 조회하여 주요 필드만 추출.

    반환: {
        "claims": list[str],                # 청구항 본문 (순서 유지)
        "abstract": str,                    # 초록 전문 (빈 문자열 가능)
        "cited_patents": list[str],         # 선행문헌 번호 목록
        "legal_status_history": list[dict], # 법적상태 이력 (향후 확장용, 현재는 원본 dict 보존)
    }
    - 네트워크·파싱 실패나 빈 응답 시 None 반환 (예외는 삼켜 로깅만).
    - 호출자는 None이면 기존 freeSearch 결과를 그대로 유지해야 함.
    """
    if not application_number:
        return None

    try:
        resp = _kipris_get_detail(application_number)
    except Exception as e:
        logger.warning("상세조회 네트워크 실패 (%s): %s", application_number, e)
        return None

    try:
        parsed = xmltodict.parse(resp.text)
    except Exception as e:
        logger.warning("상세조회 XML 파싱 실패 (%s): %s", application_number, e)
        return None

    try:
        item = (
            parsed.get("response", {})
            .get("body", {})
            .get("item")
        )
        if not item:
            logger.info("상세조회 응답에 item 없음 (%s)", application_number)
            return None

        # ── 청구항 ───────────────────────────────────────
        claim_nodes = _ensure_list(
            (item.get("claimInfoArray") or {}).get("claimInfo")
        )
        claims: list[str] = []
        for node in claim_nodes:
            if not isinstance(node, dict):
                continue
            text = (node.get("claim") or "").strip()
            if text:
                claims.append(text)

        # ── 초록 ─────────────────────────────────────────
        abs_info = (item.get("abstractInfoArray") or {}).get("abstractInfo")
        # abstractInfo는 보통 단수 dict지만 방어적으로 리스트 가능성 처리
        if isinstance(abs_info, list):
            abs_info = abs_info[0] if abs_info else None
        abstract = ""
        if isinstance(abs_info, dict):
            abstract = (abs_info.get("astrtCont") or "").strip()

        # ── 선행문헌 ─────────────────────────────────────
        prior_nodes = _ensure_list(
            (item.get("priorArtDocumentsInfoArray") or {}).get("priorArtDocumentsInfo")
        )
        cited_patents: list[str] = []
        for node in prior_nodes:
            if not isinstance(node, dict):
                continue
            num = (node.get("documentsNumber") or "").strip()
            if num:
                cited_patents.append(num)

        # ── 법적상태 이력 (원본 dict 유지) ──────────────
        legal_nodes = _ensure_list(
            (item.get("legalStatusInfoArray") or {}).get("legalStatusInfo")
        )
        legal_status_history = [n for n in legal_nodes if isinstance(n, dict)]

        return {
            "claims": claims,
            "abstract": abstract,
            "cited_patents": cited_patents,
            "legal_status_history": legal_status_history,
        }

    except Exception as e:
        logger.warning("상세조회 필드 추출 실패 (%s): %s", application_number, e)
        return None

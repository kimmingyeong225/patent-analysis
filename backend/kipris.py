import logging
import time

import requests
import xmltodict
from config import KIPRIS_API_KEY

logger = logging.getLogger(__name__)

# KIPRIS 특허/실용신안 무료 검색 서비스 URL (예시)
KIPRIS_SEARCH_URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"


def _kipris_get(params: dict, timeout: int = 15, max_attempts: int = 3) -> requests.Response:
    """KIPRIS GET 요청. 타임아웃/연결오류/5xx 에 한해 지수 백오프 재시도.
    4xx는 재시도 없이 즉시 raise (요청 자체가 잘못된 경우).
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(KIPRIS_SEARCH_URL, params=params, timeout=timeout)
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
                "similarity_score": round(0.95 - (idx * 0.05), 2),
                "공개등록공보": {
                    "patent_id": patent_id,
                    "application_number": item.get('ApplicationNumber', patent_id),
                    "title": item.get('InventionName', '제목 없음'),
                    "applicant": item.get('Applicant', '출원인 정보 없음'),
                    "inventor": item.get('Inventor', '발명자 정보 없음'),
                    "application_date": item.get('ApplicationDate', ''),
                    "publication_date": item.get('OpeningDate', ''),
                    "registration_date": item.get('RegistrationDate', None),
                    "abstract": item.get('Abstract', '요약이 제공되지 않았습니다.'),
                    "claims": ["청구범위 정보는 상세조회 API에서 확인 가능합니다."],
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

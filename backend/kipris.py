import requests
import xmltodict
from config import KIPRIS_API_KEY

# KIPRIS 특허/실용신안 무료 검색 서비스 URL (예시)
KIPRIS_SEARCH_URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"

def fetch_patent_data_from_kipris(query: str):
    """
    KIPRIS API를 호출하여 특허 검색 결과를 XML에서 JSON(dict)으로 파싱
    """
    params = {
        "word": query,
        "accessKey": KIPRIS_API_KEY,
        "docsStart": "1",
        "docsCount": "5" # 상위 5개 정도만 가져오기
    }
    
    try:
        response = requests.get(KIPRIS_SEARCH_URL, params=params)
        response.raise_for_status() # 오류 발생시 예외 처리
        
        # XML to Dictionary 변환
        xml_dict = xmltodict.parse(response.text)
        return parse_kipris_dict_to_json(xml_dict)
    except Exception as e:
        print(f"KIPRIS API Error: {e}")
        # 오류 발생 시 빈 리스트 또는 모의 데이터를 반환할 수 있음
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
        items = xml_dict.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
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
            
            patent_id = item.get('applicationNumber', f"UNKNOWN-{idx}")
            ipc_codes = item.get('ipcNumber', '알수없음').split('|')
            ipc_list = [{"code": code.strip(), "desc": ""} for code in ipc_codes if code.strip()]

            mapped_item = {
                "rank": idx + 1,
                "similarity_score": round(0.95 - (idx * 0.05), 2), # 임의의 유사점수 구현 (이후 FAISS 대체)
                "공개등록공보": {
                    "patent_id": patent_id,
                    "application_number": patent_id,
                    "title": item.get('inventionTitle', '제목 없음'),
                    "applicant": item.get('applicantName', '출원인 정보 없음'),
                    "inventor": item.get('inventorName', '발명자 정보 없음'), # FreeSearch에서는 미제공일 수 있음
                    "application_date": item.get('applicationDate', ''),
                    "publication_date": item.get('openDate', ''), # KIPRIS에서는 openDate라는 태그 사용
                    "registration_date": item.get('registerDate', None),
                    "abstract": item.get('astrtCont', '요약이 제공되지 않았습니다.'), 
                    "claims": ["청구범위 정보는 상세조회 API에서 확인 가능합니다."], # 무료 검색에서는 보통 생략됨
                    "doc_type": "공개" if not item.get('registerDate') else "등록"
                },
                "인용문헌": {
                    "cited_by_count": 0,
                    "citing_count": 0,
                    "cited_patents": []
                },
                "법적상태": {
                    "status": item.get('Lgstcs', '상태 알 수 없음'), # 특허실용행정처분
                    "status_code": "R0000",
                    "last_event": item.get('Lgstcs', ''),
                    "last_event_date": item.get('applicationDate', ''),
                    "is_alive": True if item.get('Lgstcs') in ['등록', '공개'] else False
                },
                "분류코드": {
                    "ipc": ipc_list,
                    "cpc": [] 
                }
            }
            results.append(mapped_item)
            
    except Exception as e:
        print(f"Parsing Error: {e}")
        
    return results

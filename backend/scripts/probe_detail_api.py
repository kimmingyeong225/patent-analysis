# KIPRIS 상세조회 API 프로브 스크립트
# - 실제 응답 구조(특히 청구항 태그명)를 확인하기 위한 1회성 호출 도구
# - 본 구현 전에 수동 실행하여 응답을 사람이 확인하는 용도
#
# 실행:
#   python backend/scripts/probe_detail_api.py
#   python backend/scripts/probe_detail_api.py 1020230012345
#
# 환경변수:
#   KIPRIS_API_KEY — .env 또는 시스템 env에 설정되어 있어야 함

import os
import sys
from pprint import pprint

# backend 디렉토리를 sys.path에 추가하여 config를 재사용
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import requests
import xmltodict
from config import KIPRIS_API_KEY


# 상세조회 전용 URL/파라미터 — 기존 freeSearchInfo와 베이스·키필드가 다름 (주의)
DETAIL_URL = (
    "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/"
    "getBibliographyDetailInfoSearch"
)

# 기본 샘플 출원번호 — CLI 인자로 재정의 가능
DEFAULT_APPLICATION_NUMBER = "1020230012345"


def probe(application_number: str) -> None:
    if not KIPRIS_API_KEY:
        print("[ERROR] KIPRIS_API_KEY가 설정되지 않았습니다 (.env 확인).")
        sys.exit(1)

    params = {
        "applicationNumber": application_number,
        "ServiceKey": KIPRIS_API_KEY,  # 주의: 대문자 S
    }

    print("=" * 70)
    print(f"[PROBE] GET {DETAIL_URL}")
    print(f"[PROBE] applicationNumber = {application_number}")
    print("=" * 70)

    try:
        resp = requests.get(DETAIL_URL, params=params, timeout=20)
    except requests.RequestException as e:
        print(f"[ERROR] 요청 실패: {e}")
        sys.exit(2)

    print(f"[HTTP] status = {resp.status_code}")
    print(f"[HTTP] content-type = {resp.headers.get('Content-Type', '')}")
    print(f"[HTTP] body length = {len(resp.text)} bytes")
    print("-" * 70)

    # 원문 일부도 확인 (XML 태그명 직관적으로 보기 위함)
    print("[RAW XML — 앞 2000자]")
    print(resp.text[:2000])
    print("-" * 70)

    # dict 변환 후 전체 출력
    try:
        parsed = xmltodict.parse(resp.text)
    except Exception as e:
        print(f"[ERROR] XML 파싱 실패: {e}")
        sys.exit(3)

    print("[PARSED DICT — 전체]")
    pprint(parsed, width=120, sort_dicts=False)
    print("=" * 70)
    print("[HINT] claims 후보 태그명 확인 포인트:")
    print("  - response.body.item.claimInfoArray.claimInfo[*].claim")
    print("  - response.body.item.ClaimScope / Claim / ClaimText 등")
    print("  abstract 전문 위치도 함께 확인.")


if __name__ == "__main__":
    app_num = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_APPLICATION_NUMBER
    probe(app_num)

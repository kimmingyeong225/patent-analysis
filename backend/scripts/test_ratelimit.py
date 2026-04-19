# 레이트 리밋 수동 검증 스크립트
# - 서버가 http://127.0.0.1:8000 에서 실행 중이어야 함
# - /analyze 12회 빠르게 호출 → 기본 10/minute 리밋 초과 분은 429 응답
#
# 실행:
#   python backend/scripts/test_ratelimit.py
#   python backend/scripts/test_ratelimit.py http://localhost:8000  # URL 오버라이드
#
# 서버 기동 예시 (별도 터미널):
#   cd backend && uvicorn main:app --reload

import sys
import time

import requests


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    endpoint = f"{base_url}/analyze"

    # 빈 patents 는 LLM 호출까진 가지만 비용 최소 (실제 200 응답 확인 가능)
    # 429 판정만 필요하면 USE_MOCK=true 로 서버 기동해도 무관.
    hits_200 = 0
    hits_429 = 0
    other: list[int] = []

    print(f"[*] POST {endpoint} × 12회 (0.1초 간격)")
    print(f"[*] 기본 /analyze 리밋 10/minute → 11번째부터 429 예상\n")

    for i in range(12):
        try:
            r = requests.post(
                endpoint,
                json={"user_idea": f"테스트 아이디어 {i}", "patents": []},
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"[{i+1}/12] request 실패: {e}")
            return 2

        code = r.status_code
        if code == 200:
            hits_200 += 1
        elif code == 429:
            hits_429 += 1
        else:
            other.append(code)

        retry_after = r.headers.get("Retry-After") or r.headers.get("retry-after")
        extra = f" Retry-After={retry_after}" if code == 429 else ""
        print(f"[{i+1}/12] status={code}{extra}")

        time.sleep(0.1)

    print(f"\n[집계] 200: {hits_200}, 429: {hits_429}, 기타: {other}")

    # 기본값(10/minute) 기준 판정 — RATE_LIMIT_ANALYZE 를 바꿨다면 숫자 조정 필요
    if hits_200 >= 1 and hits_429 >= 1:
        print("[OK] 레이트 리밋 동작 확인")
        return 0
    print("[WARN] 리밋이 예상대로 트리거되지 않음 — env/서버 상태 확인")
    return 1


if __name__ == "__main__":
    sys.exit(main())

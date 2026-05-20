"""Phase 1-C 검증 스크립트."""
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"


def test_search(query: str, label: str):
    print(f"\n{'='*60}")
    print(f"[{label}] query = {query!r}")
    print('='*60)
    resp = requests.post(
        f"{BASE_URL}/search",
        json={"query": query, "max_results": 3},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    print(f"cached: {data['cached']}")
    print(f"결과 수: {len(data['results'])}")
    for i, r in enumerate(data["results"]):
        pub = r["공개등록공보"]
        claims = pub.get("claims") or []
        first = claims[0] if claims else "(비어있음)"
        print(f"\n[{i+1}위] {pub['title'][:50]}")
        print(f"  출원번호: {pub.get('application_number', 'N/A')}")
        print(f"  claims 개수: {len(claims)}")
        print(f"  claims[0]: {first[:100]}")
        if first.startswith("청구범위 정보는 상세조회"):
            print("  [!] PLACEHOLDER 감지 - 상세조회 실패 또는 stale 미감지")
        elif claims and any(first.startswith(str(n)) for n in range(1, 10)):
            print("  [OK] 실제 청구항 본문으로 판단됨")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "헥사펩타이드 화장료"
    test_search(query, "1st call")
    test_search(query, "2nd call (cache hit expected)")
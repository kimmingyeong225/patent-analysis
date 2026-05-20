"""Phase 1-C DB 캐시 저장 상태 진단 스크립트."""
import sqlite3
import sys
from pathlib import Path

# backend/patents.db 위치 추정 (스크립트 위치 기준 ../)
DB_PATH = Path(__file__).resolve().parent.parent / "patents.db"

if not DB_PATH.exists():
    # 프로젝트 루트에 있을 수도 있음
    alt = Path(__file__).resolve().parent.parent.parent / "patents.db"
    if alt.exists():
        DB_PATH = alt
    else:
        print(f"[ERR] patents.db 없음. 찾은 경로: {DB_PATH}, {alt}")
        sys.exit(1)

print(f"[INFO] DB 경로: {DB_PATH}")
print(f"[INFO] 크기: {DB_PATH.stat().st_size:,} bytes")
print()

query = sys.argv[1] if len(sys.argv) > 1 else "헥사펩타이드 화장료"
print(f"[INFO] 검증 쿼리: {query!r}")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. 전체 테이블 목록
print("\n[1] 테이블 목록:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r["name"] for r in cur.fetchall()]
print(f"    {tables}")

# 2. 각 테이블 행 수
print("\n[2] 각 테이블 총 행 수:")
for t in tables:
    cur.execute(f"SELECT COUNT(*) AS c FROM {t}")
    print(f"    {t}: {cur.fetchone()['c']}")

# 3. 대상 쿼리의 SearchResult 매핑
print(f"\n[3] search_results WHERE query = {query!r}:")
cur.execute("SELECT COUNT(*) AS c FROM search_results WHERE query = ?", (query,))
sr_count = cur.fetchone()["c"]
print(f"    행 수: {sr_count}")

if sr_count > 0:
    cur.execute(
        "SELECT patent_id, rank, similarity_score FROM search_results "
        "WHERE query = ? ORDER BY rank ASC LIMIT 5",
        (query,),
    )
    for row in cur.fetchall():
        print(f"    rank={row['rank']} pid={row['patent_id']} score={row['similarity_score']}")

    # 4. 연결된 Patent의 claims 상태
    print(f"\n[4] 해당 patent들의 claims 저장 상태:")
    cur.execute(
        """
        SELECT p.patent_id, p.title, p.claims
        FROM patents p
        JOIN search_results sr ON sr.patent_id = p.patent_id
        WHERE sr.query = ?
        ORDER BY sr.rank ASC
        LIMIT 5
        """,
        (query,),
    )
    for row in cur.fetchall():
        claims_raw = row["claims"] or ""
        # JSON 문자열일 수도 있고, list repr일 수도
        preview = claims_raw[:120] if isinstance(claims_raw, str) else str(claims_raw)[:120]
        print(f"\n    [{row['patent_id']}] {(row['title'] or '')[:40]}")
        print(f"       claims type: {type(claims_raw).__name__}, len: {len(claims_raw) if claims_raw else 0}")
        print(f"       preview: {preview}")

        is_placeholder = "청구범위 정보는 상세조회" in preview
        print(f"       placeholder 포함: {is_placeholder}")
else:
    print("    [!] 해당 쿼리의 SearchResult가 없음 — save_search_results 실패 또는 미호출")

# 5. 전체 search_results 쿼리 목록 (어떤 쿼리들이 저장돼 있는지)
print(f"\n[5] 저장된 고유 쿼리 목록 (최대 10개):")
cur.execute("SELECT query, COUNT(*) AS c FROM search_results GROUP BY query LIMIT 10")
for row in cur.fetchall():
    marker = "  ★" if row["query"] == query else ""
    print(f"    [{row['c']:>3}건] {row['query']}{marker}")

conn.close()
print("\n" + "=" * 70)
print("[DONE] 진단 완료")
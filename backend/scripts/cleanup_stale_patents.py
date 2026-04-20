# 오염된 Patent 레코드 일회성 정리 스크립트
# - Phase 1-C 이전에 저장된 placeholder claims 행을 식별해 관련 테이블까지 일괄 삭제
# - 수동으로 1회 실행. 일상 런타임에서는 쓰지 않음.
#
# 실행:
#   python backend/scripts/cleanup_stale_patents.py
#   python backend/scripts/cleanup_stale_patents.py --yes   # 확인 프롬프트 스킵
#
# 원리:
#   1) patents.claims 가 placeholder 문자열을 포함하는 patent_id 수집
#   2) 자식 테이블(classifications/citations/legal_statuses/search_results) 먼저 삭제
#   3) 마지막으로 patents 삭제
#   4) 단일 트랜잭션 — 중간 실패 시 rollback

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# DB 경로 자동 해석 — 프로젝트 루트에서 실행해도 backend/patents.db를 찾도록 보정.
# 사용자가 명시적으로 DATABASE_URL을 지정했다면 존중.
if not os.environ.get("DATABASE_URL"):
    _DEFAULT_DB = os.path.join(_BACKEND_DIR, "patents.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = f"sqlite:///{_DEFAULT_DB}"

from sqlalchemy import text

import models
from database import SessionLocal
from kipris import STALE_CLAIMS_PLACEHOLDER


# placeholder 판정 prefix — crud._STALE_PREFIX와 동일 규칙 (앞 20자).
_STALE_PREFIX = STALE_CLAIMS_PLACEHOLDER[:20]


def find_stale_patent_ids(session) -> list[str]:
    """claims가 placeholder로 시작하는 patent_id 목록.

    SQLAlchemy JSON 컬럼은 ensure_ascii=True로 직렬화되어 SQL 측에선 \\uXXXX
    이스케이프된 문자열이 됨. raw text 쿼리로 읽으면 디코딩이 안 되므로,
    ORM 경로(Patent.claims — JSON 자동 디코딩)를 사용해 Python 리스트로 받아
    prefix 매칭한다. Patent 수천 건 규모에선 충분히 빠름.
    """
    rows = session.query(models.Patent.patent_id, models.Patent.claims).all()
    stale: list[str] = []
    for patent_id, claims in rows:
        if not patent_id:
            continue
        if not claims or not isinstance(claims, list):
            continue
        first = claims[0] if isinstance(claims[0], str) else ""
        if first.startswith(_STALE_PREFIX):
            stale.append(patent_id)
    return stale


def _delete_by_patent_ids(session, table: str, ids: list[str]) -> int:
    """지정 테이블에서 patent_id IN (...) 행 삭제. 반환: 삭제 건수.
    SQLite의 파라미터 바인딩 한계를 피하기 위해 500건씩 청크로 실행.
    """
    if not ids:
        return 0
    BATCH = 500
    total = 0
    for i in range(0, len(ids), BATCH):
        chunk = ids[i : i + BATCH]
        placeholders = ",".join(f":id{j}" for j in range(len(chunk)))
        params = {f"id{j}": pid for j, pid in enumerate(chunk)}
        result = session.execute(
            text(f"DELETE FROM {table} WHERE patent_id IN ({placeholders})"),
            params,
        )
        total += result.rowcount or 0
    return total


def main() -> int:
    auto_yes = "--yes" in sys.argv or "-y" in sys.argv

    session = SessionLocal()
    try:
        stale_ids = find_stale_patent_ids(session)
        n = len(stale_ids)

        if n == 0:
            print("정리 대상 없음 — DB에 placeholder claims 행이 없습니다.")
            return 0

        print(f"[스캔] placeholder claims 행: {n} 건")
        if n <= 20:
            for pid in stale_ids:
                print(f"  - {pid}")
        else:
            for pid in stale_ids[:10]:
                print(f"  - {pid}")
            print(f"  ... ({n - 10}건 더)")

        if not auto_yes:
            answer = input(f"\n{n} 건 및 자식 레코드 삭제합니다. 계속? [y/N]: ").strip().lower()
            if answer != "y":
                print("취소됨.")
                return 0

        # 자식부터 역순 삭제 (FK CASCADE 미설정 — 순서 중요)
        counts: dict[str, int] = {}
        for table in (
            "classifications",
            "citations",
            "legal_statuses",
            "search_results",
            "patents",  # 마지막
        ):
            counts[table] = _delete_by_patent_ids(session, table, stale_ids)

        session.commit()
        print(
            "[완료] Deleted: "
            f"patents={counts['patents']}, "
            f"search_results={counts['search_results']}, "
            f"classifications={counts['classifications']}, "
            f"citations={counts['citations']}, "
            f"legal_statuses={counts['legal_statuses']}"
        )
        return 0

    except Exception as e:
        session.rollback()
        print(f"[ERROR] 트랜잭션 실패, rollback 완료: {e}", file=sys.stderr)
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())

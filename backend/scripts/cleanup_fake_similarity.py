# Phase 1-F.1: legacy 가짜 similarity_score 탐지 스크립트 (dry-run 전용)
#
# 배경:
#   Phase 1-F 이전 `kipris.parse_kipris_dict_to_json`는
#   `similarity_score = round(0.95 - idx*0.05, 2)` 형태의 rank-based 가짜 점수를
#   생성했고, FAISS가 성공하면 덮어써졌지만 FAISS 실패 시 그대로 DB에 저장됐다.
#   해당 row는 UI에서 실제 의미 없는 95%/90%... 로 노출되므로 진단/정리가 필요.
#
# 대상 테이블: search_results (patents 테이블에는 similarity_score 없음)
# 탐지 방법: similarity_score == round(0.95 - (rank-1)*0.05, 2) 페어 매칭
#   - float 동등 비교의 미세 오차 대비 abs(diff) < 1e-9 허용
#   - rank 또는 similarity_score 가 NULL 이면 건너뜀
#
# 안전 정책: --dry-run 만 제공. --apply 는 의도적으로 미구현.
#   실제 정리는 사용자가 수동 SQL 또는 별도 스크립트로 수행.
#
# 실행:
#   python backend/scripts/cleanup_fake_similarity.py
#   python backend/scripts/cleanup_fake_similarity.py --dry-run   # 동일 (기본값)

import argparse
import os
import sys
from collections import defaultdict

# Windows 기본 콘솔 인코딩(cp949)에서 em-dash 등 확장 유니코드 출력 시
# UnicodeEncodeError 발생 → stdout/stderr 를 UTF-8 로 재설정.
# Python 3.7+ 에서 지원. 실패해도 치명적이지 않으므로 조용히 폴백.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# DB 경로 자동 해석 — 프로젝트 루트에서 실행해도 backend/patents.db 를 찾도록.
# 사용자가 명시적으로 DATABASE_URL을 지정했다면 존중.
if not os.environ.get("DATABASE_URL"):
    _DEFAULT_DB = os.path.join(_BACKEND_DIR, "patents.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = f"sqlite:///{_DEFAULT_DB}"

import models  # noqa: F401  — SQLAlchemy 메타데이터 로드용
from database import SessionLocal

_EPS = 1e-9


def _expected_legacy_score(rank: int) -> float:
    """Phase 1-F 이전 kipris.parse 의 가짜 점수 공식.
    idx = rank - 1 이므로 round(0.95 - (rank-1)*0.05, 2).
    """
    return round(0.95 - (rank - 1) * 0.05, 2)


def find_legacy_rows(session):
    """(query, patent_id, rank, similarity_score) 튜플 목록 반환.
    rank/similarity_score NULL 또는 페어 불일치 row 는 제외.
    """
    rows = session.query(
        models.SearchResult.query,
        models.SearchResult.patent_id,
        models.SearchResult.rank,
        models.SearchResult.similarity_score,
    ).all()

    legacy = []
    for query, patent_id, rank, score in rows:
        if rank is None or score is None:
            continue
        expected = _expected_legacy_score(rank)
        if abs(score - expected) < _EPS:
            legacy.append((query, patent_id, rank, score))
    return legacy


def main() -> int:
    parser = argparse.ArgumentParser(
        description="legacy 가짜 similarity_score 탐지 (dry-run 전용)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="탐지만 수행, 실제 수정 없음 (기본값)",
    )
    parser.parse_args()

    session = SessionLocal()
    try:
        total = session.query(models.SearchResult).count()
        legacy = find_legacy_rows(session)
        n = len(legacy)

        print("=" * 60)
        print("legacy 가짜 similarity_score 탐지 (dry-run)")
        print("=" * 60)
        print(f"search_results 전체 행: {total}")
        print(f"legacy 페어 매칭 행:    {n}")
        print()

        if n == 0:
            print("정리 대상 없음 — 페어 매칭되는 legacy row 가 없습니다.")
            return 0

        # 쿼리별 집계
        by_query: dict[str, int] = defaultdict(int)
        for query, _, _, _ in legacy:
            by_query[query] += 1

        print(f"[쿼리별 집계] ({len(by_query)} 개 쿼리)")
        for q, cnt in sorted(by_query.items(), key=lambda kv: -kv[1]):
            print(f"  - '{q}': {cnt} 건")
        print()

        # 샘플 20개 (query, rank, patent_id, score)
        sample_n = min(20, n)
        print(f"[샘플 {sample_n}/{n}]")
        print(f"  {'query':<24} {'rank':>4} {'patent_id':<24} {'score':>6}")
        for query, pid, rank, score in legacy[:sample_n]:
            q_trunc = (query or "")[:22] + (".." if query and len(query) > 22 else "")
            print(f"  {q_trunc:<24} {rank:>4} {(pid or '')[:22]:<24} {score:>6.2f}")

        print()
        print("=" * 60)
        print("이 스크립트는 --dry-run 전용입니다. 실제 정리는 수동 SQL 로 수행하세요.")
        print("권장 SQL (Q2=(c) 기준 가이드 — 실행은 사용자 판단):")
        print("  UPDATE search_results SET similarity_score = 0.0")
        print("    WHERE <위 페어 매칭 조건>;  -- Python 조건을 SQL 로 옮길 때 주의")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"[ERROR] 탐지 실패: {e}", file=sys.stderr)
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())

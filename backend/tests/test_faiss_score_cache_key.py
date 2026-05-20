# Phase 2-A.2: _apply_faiss_scores 캐시 키 정합성 검증
#
# 배경: 이전 구현에서 캐시 키가 query 단독이라 같은 query + 다른 patents
# 동시 요청 시 patents_A 기반 (index, chunks) 가 patents_B 호출에 재사용되어
# patents_B 의 patent_id 가 chunks_A 에 없으면 score=0.0 으로 잘못 표시.
# 본 fix 는 키를 query + patent_id 해시로 강화 (main.py _apply_faiss_scores).
#
# 4개 시나리오:
#   1. test_faiss_score_different_patents_no_collision   — 같은 query 다른 patents → 2 cache entry
#   2. test_faiss_score_same_patents_cache_hit           — 같은 query 같은 patents → 1 entry, build 1회 (회귀 가드)
#   3. test_faiss_score_filter_then_score_no_mismatch    — A.2 USE_MOCK 분기 시나리오 직접 재현
#   4. test_faiss_score_max_results_variance_no_mismatch — A.3 KIPRIS 분기 시나리오 직접 재현
#
# 기존 test_faiss_cache_concurrency.py (5건) 는 _get_or_build_faiss_index 직접 호출 +
# string key 인자라 본 변경 (캐시 키 생성 로직은 _apply_faiss_scores 내부) 영향 없음.
# 기존 test_search_source.py 4건은 _apply_faiss_scores 자체를 lambda 로 monkeypatch 하므로
# 본 변경 (함수 내부) 영향 없음.
#
# 실행:
#   python -m pytest backend/tests/test_faiss_score_cache_key.py -v

import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")


def _reload_app():
    """환경변수 변경 후 main/config 를 깨끗이 다시 로드.

    재import 시 _faiss_cache / _faiss_key_locks 는 빈 dict 로 초기화 → 테스트 격리.
    """
    for mod in ("config", "main", "cache", "limiter"):
        if mod in sys.modules:
            del sys.modules[mod]
    import main  # noqa: F401
    # merge (feature/embedding ⊕ feature/ui-llm): 영어 sentinel query
    # (__phase*) 가 production 의 OpenAI 호출로 cache key 변경되는 회귀 차단.
    # 한국어 query 는 is_korean=True 분기로 stub 영향 0. monkeypatch 미사용 —
    # 다음 _reload_app() 호출이 main 재로딩 시 stub 도 재적용 (self-managed).
    main.translate_to_korean = lambda x: x
    return sys.modules["main"]


def _make_patent(pid: str) -> dict:
    """테스트용 최소 patent dict — _apply_faiss_scores 가 참조하는 키만 포함."""
    return {
        "공개등록공보": {
            "patent_id": pid,
            "title": f"Title-{pid}",
            "abstract": f"Abstract for {pid}",
            "claims": [f"Claim for {pid}"],
        }
    }


def _mock_embedding_helpers(main, monkeypatch, score_for_pid):
    """embedding 모듈 의존 헬퍼 3종을 main 모듈 namespace 에서 mock.

    chunk_patents     : patents → [{patent_id, section, text}, ...]
    build_faiss_index : chunks → ("INDEX-N", chunks). 호출 횟수 추적.
    search_similar    : chunks 의 patent_id 별로 score_for_pid 콜러블 적용.

    반환: counters dict — {"build": 호출 횟수}
    """
    counters = {"build": 0}

    def fake_chunk_patents(patents):
        return [
            {
                "patent_id": p["공개등록공보"]["patent_id"],
                "section": "abstract",
                "text": ".",
            }
            for p in patents
        ]

    def fake_build_faiss_index(chunks):
        counters["build"] += 1
        return (f"INDEX-{counters['build']}", chunks)

    def fake_search_similar(query, index, chunks, top_k):
        return [
            {
                "patent_id": c["patent_id"],
                "similarity_score": score_for_pid(c["patent_id"]),
            }
            for c in chunks
        ]

    monkeypatch.setattr(main, "chunk_patents", fake_chunk_patents)
    monkeypatch.setattr(main, "build_faiss_index", fake_build_faiss_index)
    monkeypatch.setattr(main, "search_similar", fake_search_similar)
    return counters


def test_faiss_score_different_patents_no_collision(monkeypatch):
    """같은 query 라도 다른 patents → 다른 cache_key → 2 entry, 각자 정확한 score.

    핵심 가드 — 옵션 5 (no-op) 라면 1 entry 로 합쳐져 patents_B score=0.0 발생.
    """
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)
    counters = _mock_embedding_helpers(main, monkeypatch, lambda pid: 0.7)

    patents_A = [_make_patent(p) for p in ["A1", "A2", "A3"]]
    patents_B = [_make_patent(p) for p in ["B1", "B2", "B3"]]

    query = "__phase2a2_score_diff__"
    main._apply_faiss_scores(patents_A, query)
    main._apply_faiss_scores(patents_B, query)

    # 두 호출이 서로 다른 cache_key 를 만들었어야 함
    assert len(cache._faiss_cache) == 2, (
        f"cache entry count={len(cache._faiss_cache)} (기대: 2). 키가 합쳐졌으면 1."
    )
    # build 도 2회 (각자 자기 chunks 로)
    assert counters["build"] == 2, f"build count={counters['build']} (기대: 2)"

    # 각 patents 의 모든 항목이 자기 patent_id score 로 매핑됨 (0.0 잔여 없음)
    assert all(p["similarity_score"] == 0.7 for p in patents_A)
    assert all(p["similarity_score"] == 0.7 for p in patents_B)


def test_faiss_score_same_patents_cache_hit(monkeypatch):
    """같은 query + 같은 patents → cache_key 동일 → 2회차는 build 호출 0 (회귀 가드).

    Phase 1-G hot path 보존 검증: 정상 케이스에서는 캐시 효율 동일.
    """
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)
    counters = _mock_embedding_helpers(main, monkeypatch, lambda pid: 0.9)

    patents_template = [_make_patent(p) for p in ["X1", "X2", "X3"]]
    query = "__phase2a2_score_same__"

    # 1차 호출 — build 1회
    # _apply_faiss_scores 는 in-place sort 하므로 매 호출에 새 리스트 전달
    main._apply_faiss_scores(list(patents_template), query)
    assert counters["build"] == 1

    # 2차 호출 — 같은 patents_id 시퀀스 → cache hit, build 미호출
    main._apply_faiss_scores(list(patents_template), query)
    assert counters["build"] == 1, (
        f"2차 호출에서 build 가 또 일어남 (count={counters['build']}). "
        f"같은 patents 면 키 동일 → cache hit 이어야 함."
    )
    assert len(cache._faiss_cache) == 1


def test_faiss_score_filter_then_score_no_mismatch(monkeypatch):
    """A.2 USE_MOCK 분기 시나리오 재현 — 같은 query 다른 필터 결과로 patents 다름.

    이전 옵션 5: patents_B 의 patent_id 가 chunks_A 에 없어 score=0.0 다수.
    Phase 2-A.2: 각 호출이 자기 patents 기반 cache entry → 모든 항목 score 정상.

    main.py:210 _apply_filters → main.py:211 _apply_faiss_scores 순서 시뮬레이션:
    같은 query "__phase2a2_score_filter__" 로 두 다른 필터 결과 (patents_filter_A,
    patents_filter_B) 가 _apply_faiss_scores 에 진입. 이전이라면 1차 cache 가 2차에
    재사용돼 patents_filter_B 의 patents_filter_A 에 없는 ID (F4, F5) score=0.0.
    """
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)
    _mock_embedding_helpers(main, monkeypatch, lambda pid: 0.8)

    # filter_A 결과 (e.g., year_from=2020 통과): F1, F2, F3
    patents_filter_A = [_make_patent(p) for p in ["F1", "F2", "F3"]]
    # filter_B 결과 (e.g., year_from=2010 통과): F2 만 겹치고 F4, F5 신규
    patents_filter_B = [_make_patent(p) for p in ["F2", "F4", "F5"]]

    query = "__phase2a2_score_filter__"
    main._apply_faiss_scores(patents_filter_A, query)
    main._apply_faiss_scores(patents_filter_B, query)

    # 두 호출 각각 자기 patents 기반 score → 0.0 잔여 0
    assert all(p["similarity_score"] == 0.8 for p in patents_filter_A)
    assert all(p["similarity_score"] == 0.8 for p in patents_filter_B)
    # 핵심 가드: F4, F5 (filter_A 에 없음) 도 정확한 0.8 — 이전 옵션 5 라면 0.0
    pids_B = {p["공개등록공보"]["patent_id"] for p in patents_filter_B}
    assert {"F4", "F5"}.issubset(pids_B)
    f4_score = next(p["similarity_score"] for p in patents_filter_B if p["공개등록공보"]["patent_id"] == "F4")
    f5_score = next(p["similarity_score"] for p in patents_filter_B if p["공개등록공보"]["patent_id"] == "F5")
    assert f4_score == 0.8, f"F4 score={f4_score} (기대: 0.8). 캐시 키 결함 잔존 신호."
    assert f5_score == 0.8, f"F5 score={f5_score} (기대: 0.8). 캐시 키 결함 잔존 신호."

    # 두 호출이 별개 cache entry
    assert len(cache._faiss_cache) == 2


def test_faiss_score_max_results_variance_no_mismatch(monkeypatch):
    """A.3 KIPRIS 분기 시나리오 재현 — 같은 query 다른 max_results → fetch_count 다름 → patents 길이 다름.

    main.py:225 fetch_count = max(payload.max_results * 4, 30):
      - max_results=5  → fetch_count=30
      - max_results=10 → fetch_count=40
    이전: 2차 호출이 1차 cache hit → 추가 10건 (K30~K39) score=0.0.
    Phase 2-A.2: 각 호출이 자기 cache entry → 추가 10건도 정상 score.
    """
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)
    _mock_embedding_helpers(main, monkeypatch, lambda pid: 0.6)

    # 1차: 30건 (max_results=5 → fetch_count=30 시뮬레이션)
    patents_30 = [_make_patent(f"K{i:02d}") for i in range(30)]
    # 2차: 40건 — 30건 prefix + 10건 추가 (KIPRIS 결정성 가정, B.2 프로브 결과 기반)
    patents_40 = [_make_patent(f"K{i:02d}") for i in range(40)]

    query = "__phase2a2_score_size__"
    main._apply_faiss_scores(patents_30, query)
    main._apply_faiss_scores(patents_40, query)

    # 30건 / 40건 각자 정확한 score
    assert all(p["similarity_score"] == 0.6 for p in patents_30)
    assert all(p["similarity_score"] == 0.6 for p in patents_40)
    # 핵심 가드: 추가 10건 (K30~K39) 도 0.6 — 이전이라면 cache_30 hit 으로 0.0
    extra_ids = {f"K{i:02d}" for i in range(30, 40)}
    extra_scores = [
        p["similarity_score"]
        for p in patents_40
        if p["공개등록공보"]["patent_id"] in extra_ids
    ]
    assert len(extra_scores) == 10
    assert all(s == 0.6 for s in extra_scores), (
        f"K30~K39 score={extra_scores} (모두 0.6 기대). 캐시 키 결함 잔존 신호."
    )

    # 두 호출이 별개 cache entry
    assert len(cache._faiss_cache) == 2

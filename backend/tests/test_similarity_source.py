# /similarity 응답의 source 필드 투명화 검증 (Phase 1-F.1)
#
# 5개 반환 경로 (main.py:477-523) 전부 검증:
#   A. USE_MOCK=true  + chunks 정상           → source="mock",   total_chunks>0
#   B. USE_MOCK=true  + chunks empty          → source="mock",   total_chunks=0, results=[]
#   C. USE_MOCK=false + KIPRIS empty          → source="kipris", total_chunks=0, results=[]
#   D. USE_MOCK=false + KIPRIS 정상 + chunks 정상 → source="kipris", total_chunks>0
#   E. USE_MOCK=false + KIPRIS 정상 + chunks empty→ source="kipris", total_chunks=0, results=[]
#
# B 와 E 는 동일한 line 510-512 (chunks empty) 분기에서 source 변수 보존을 양쪽에서
# 검증한다. 1-F.1 에서 제거한 mock 폴백이 부분 복구되는 회귀를 B 가 차단하고,
# E 는 KIPRIS 경로의 source 보존을 보장한다.
#
# 모킹 (옵션 2-b, 헬퍼 계약 가정):
#   - fetch_patent_data_from_kipris : 네트워크 차단, 빈/정상 결과 강제
#   - _get_or_build_faiss_index     : Optional[Tuple] 헬퍼 계약 — None / (idx, chunks)
#   - search_similar                : FAISS 검색 + embedding 호출 차단, 결정적 결과 주입
# 헬퍼 내부 (chunk_patents / build_faiss_index) 회귀는
# test_faiss_cache_concurrency.py 가 별도 커버.
#
# 실행:
#   python -m pytest backend/tests/test_similarity_source.py -v

import os
import sys

import pytest
from fastapi.testclient import TestClient

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")
# 다른 테스트의 타이트한 레이트 리밋이 오염되지 않도록 기본값으로 되돌림
os.environ["RATE_LIMIT_SIMILARITY"] = "100/minute"


def _reload_app():
    """환경변수 변경 후 main/config 를 깨끗이 다시 로드."""
    for mod in ("config", "main", "cache", "limiter"):
        if mod in sys.modules:
            del sys.modules[mod]
    import main  # noqa: F401
    return sys.modules["main"]


def _fake_chunk_results(top_k: int) -> list[dict]:
    """search_similar 의 반환 형태 — schemas.SimilarChunkItem 과 정합."""
    return [
        {
            "rank": i + 1,
            "patent_id": f"P-FAKE-{i + 1}",
            "section": "abstract",
            "text": f"청크 텍스트 {i + 1}",
            "similarity_score": 0.9 - i * 0.1,
        }
        for i in range(top_k)
    ]


def test_similarity_source_use_mock_success(monkeypatch):
    """A: USE_MOCK=true + chunks 정상 → source='mock', total_chunks>0, results 있음."""
    monkeypatch.setenv("USE_MOCK", "true")
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)

    fake_chunks = ["chunk-A", "chunk-B"]  # len=2 → total_chunks=2
    monkeypatch.setattr(
        cache, "_get_or_build_faiss_index",
        lambda query, build_fn: (object(), fake_chunks),
    )
    monkeypatch.setattr(
        main, "search_similar",
        lambda q, index, chunks, top_k: _fake_chunk_results(top_k),
    )

    client = TestClient(main.app)
    resp = client.post(
        "/similarity",
        json={"query": "__phase1f1_sim_use_mock_ok__", "top_k": 3},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "mock"
    assert body["total_chunks"] == 2
    assert len(body["results"]) == 3


def test_similarity_source_use_mock_chunks_empty(monkeypatch):
    """B: USE_MOCK=true + chunks empty → source='mock', total_chunks=0, results=[].

    line 510-512 의 chunks empty 분기에서 source='mock' 가 보존되는지 검증.
    1-F.1 에서 제거한 mock 폴백이 부분 복구되는 회귀를 차단.
    """
    monkeypatch.setenv("USE_MOCK", "true")
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)

    monkeypatch.setattr(
        cache, "_get_or_build_faiss_index",
        lambda query, build_fn: None,
    )

    client = TestClient(main.app)
    resp = client.post(
        "/similarity",
        json={"query": "__phase1f1_sim_use_mock_empty__", "top_k": 3},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "mock"
    assert body["total_chunks"] == 0
    assert body["results"] == []


def test_similarity_source_kipris_empty(monkeypatch):
    """C: USE_MOCK=false + KIPRIS empty → source='kipris', total_chunks=0, results=[].

    line 500 의 즉시 return 경로 — 1-F.1 mock 폴백 제거의 핵심 회귀 가드.
    """
    monkeypatch.setenv("USE_MOCK", "false")
    main = _reload_app()

    monkeypatch.setattr(
        main, "fetch_patent_data_from_kipris",
        lambda query, docs_count=30: [],
    )

    client = TestClient(main.app)
    resp = client.post(
        "/similarity",
        json={"query": "__phase1f1_sim_kipris_empty__", "top_k": 3},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "kipris"
    assert body["total_chunks"] == 0
    assert body["results"] == []


def test_similarity_source_kipris_success(monkeypatch):
    """D: USE_MOCK=false + KIPRIS 정상 + chunks 정상 → source='kipris', total_chunks>0.

    정상 응답 경로 (line 518-523).
    """
    monkeypatch.setenv("USE_MOCK", "false")
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)

    monkeypatch.setattr(
        main, "fetch_patent_data_from_kipris",
        lambda query, docs_count=30: [{"공개등록공보": {"patent_id": "P-1"}}],
    )
    fake_chunks = ["chunk-1", "chunk-2", "chunk-3"]  # len=3
    monkeypatch.setattr(
        cache, "_get_or_build_faiss_index",
        lambda query, build_fn: (object(), fake_chunks),
    )
    monkeypatch.setattr(
        main, "search_similar",
        lambda q, index, chunks, top_k: _fake_chunk_results(top_k),
    )

    client = TestClient(main.app)
    resp = client.post(
        "/similarity",
        json={"query": "__phase1f1_sim_kipris_ok__", "top_k": 5},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "kipris"
    assert body["total_chunks"] == 3
    assert len(body["results"]) == 5


def test_similarity_source_kipris_chunks_empty(monkeypatch):
    """E: USE_MOCK=false + KIPRIS 정상 + chunks empty → source='kipris', total_chunks=0.

    line 510-512 에서 source='kipris' 가 보존되는지 검증. B 와 짝을 이뤄
    헬퍼 None 반환 시 source 변수 변형이 없음을 USE_MOCK 양쪽에서 가드.
    """
    monkeypatch.setenv("USE_MOCK", "false")
    main = _reload_app()
    import cache  # post-reload 동기화 (Phase 3-A.1.1 stale binding 회피)

    monkeypatch.setattr(
        main, "fetch_patent_data_from_kipris",
        lambda query, docs_count=30: [{"공개등록공보": {"patent_id": "P-1"}}],
    )
    monkeypatch.setattr(
        cache, "_get_or_build_faiss_index",
        lambda query, build_fn: None,
    )

    client = TestClient(main.app)
    resp = client.post(
        "/similarity",
        json={"query": "__phase1f1_sim_kipris_chunks_empty__", "top_k": 3},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "kipris"
    assert body["total_chunks"] == 0
    assert body["results"] == []

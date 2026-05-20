# /search 응답의 source 필드 투명화 검증 (Phase 1-F)
# - USE_MOCK=true 경로 → source="mock"
# - KIPRIS 빈 결과 경로 → source="kipris", results=[] (mock 폴백 없음)
# - DB cache hit 경로 → source="cache"
#
# 실행:
#   python -m pytest backend/tests/test_search_source.py -v

import importlib
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
os.environ["RATE_LIMIT_SEARCH"] = "100/minute"


def _reload_app():
    """환경변수 변경 후 main/config를 깨끗이 다시 로드."""
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


def test_mock_branch_returns_source_mock(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "true")
    main = _reload_app()
    client = TestClient(main.app)

    resp = client.post("/search", json={"query": "테스트", "max_results": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "mock"
    assert body["cached"] is False
    assert isinstance(body["results"], list)


def test_empty_kipris_returns_source_kipris_with_empty_results(monkeypatch):
    """KIPRIS가 빈 결과를 돌려줄 때 mock으로 폴백하지 않는다.
    source="kipris", results=[], cached=False 가 즉시 반환되어야 한다.
    """
    monkeypatch.setenv("USE_MOCK", "false")
    main = _reload_app()

    # KIPRIS 호출을 강제로 빈 결과로 만듦 — 실제 네트워크 미호출
    monkeypatch.setattr(
        main, "fetch_patent_data_from_kipris", lambda query, docs_count=30: []
    )
    client = TestClient(main.app)

    resp = client.post(
        "/search",
        # 캐시 hit을 피하기 위해 테스트마다 유니크한 쿼리
        json={"query": "__phase1f_empty_probe__", "max_results": 5},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "kipris"
    assert body["cached"] is False
    assert body["results"] == []


def test_kipris_success_returns_source_kipris(monkeypatch):
    """KIPRIS가 정상 결과를 반환하는 성공 경로 → source='kipris', results 비어있지 않음.
    FAISS/embedding/DB 저장은 실패해도 OK — source 필드 검증이 목적.
    """
    monkeypatch.setenv("USE_MOCK", "false")
    main = _reload_app()

    fake_kipris_results = [
        {
            "rank": 1,
            "similarity_score": 0.0,  # parse_kipris_dict_to_json의 새 기본값
            "공개등록공보": {
                "patent_id": "P-KIPRIS-1",
                "application_number": "10-2024-900001",
                "title": "KIPRIS 성공 경로 특허",
                "applicant": "출원인A",
                "inventor": "발명자A",
                "application_date": "20240301",
                "publication_date": "20240401",
                "registration_date": None,
                "abstract": "요약",
                "claims": ["청구범위 정보는 상세조회 API에서 확인 가능합니다."],
                "doc_type": "공개",
            },
            "인용문헌": {"cited_by_count": 0, "citing_count": 0, "cited_patents": []},
            "법적상태": {
                "status": "공개",
                "status_code": "R0000",
                "last_event": "공개",
                "last_event_date": "20240401",
                "is_alive": True,
            },
            "분류코드": {"ipc": [], "cpc": []},
        }
    ]

    # KIPRIS 응답을 강제 주입 — 네트워크 미호출
    monkeypatch.setattr(
        main,
        "fetch_patent_data_from_kipris",
        lambda query, docs_count=30: list(fake_kipris_results),
    )
    # FAISS/enrich/DB 저장은 전부 no-op 으로 — source 필드 검증이 목적
    monkeypatch.setattr(main, "_apply_faiss_scores", lambda patents, query: patents)
    monkeypatch.setattr(main, "_enrich_top_patents_with_detail", lambda patents, max_workers=5: None)
    monkeypatch.setattr(main.crud, "save_search_results", lambda db, q, items: None)
    # cache miss 강제 — 이 쿼리가 다른 테스트에서 저장됐을 가능성 차단
    monkeypatch.setattr(main.crud, "get_cached_search", lambda db, q, payload: None)

    client = TestClient(main.app)
    resp = client.post(
        "/search",
        json={"query": "__phase1f_kipris_success_probe__", "max_results": 5},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "kipris"
    assert body["cached"] is False
    assert len(body["results"]) >= 1
    assert body["results"][0]["공개등록공보"]["patent_id"] == "P-KIPRIS-1"


def test_cache_hit_returns_source_cache(monkeypatch):
    """crud.get_cached_search가 리스트를 반환하면 source='cache'."""
    monkeypatch.setenv("USE_MOCK", "false")
    main = _reload_app()

    # 최소 SearchResultItem 형태 — schemas.PatentInfo 기본값 대부분 허용
    fake_item = {
        "rank": 1,
        "similarity_score": 0.42,
        "공개등록공보": {
            "patent_id": "P-CACHE-1",
            "application_number": "10-2024-000001",
            "title": "캐시 테스트 특허",
            "applicant": "테스트출원인",
            "inventor": "테스트발명자",
            "application_date": "20240101",
            "publication_date": "20240201",
            "registration_date": None,
            "abstract": "요약",
            "claims": ["청구항 1"],
            "doc_type": "공개",
        },
        "인용문헌": {"cited_by_count": 0, "citing_count": 0, "cited_patents": []},
        "법적상태": {
            "status": "공개",
            "status_code": "R0000",
            "last_event": "공개",
            "last_event_date": "20240201",
            "is_alive": True,
        },
        "분류코드": {"ipc": [], "cpc": []},
    }
    monkeypatch.setattr(
        main.crud, "get_cached_search", lambda db, q, payload: [fake_item]
    )
    client = TestClient(main.app)

    resp = client.post(
        "/search",
        json={"query": "__phase1f_cache_probe__", "max_results": 3},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "cache"
    assert body["cached"] is True
    assert len(body["results"]) == 1
    assert body["results"][0]["공개등록공보"]["patent_id"] == "P-CACHE-1"

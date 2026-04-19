# 레이트 리밋 검증 (slowapi + FastAPI TestClient)
# - /analyze 를 RATE_LIMIT_ANALYZE 횟수+1 만큼 연속 호출 → 초과분 429
# - 429 응답에 Retry-After 헤더 포함 여부
# - LLM 호출은 monkeypatch 로 네트워크 차단
#
# 실행:
#   cd backend && python -m pytest tests/test_rate_limit.py -v

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# import 전에 mock 모드로 — KIPRIS/OpenAI 실제 호출 방지
os.environ.setdefault("USE_MOCK", "true")
os.environ.setdefault("OPENAI_API_KEY", "test-dummy")
# 테스트 전용 타이트한 리밋 (빠르게 초과 도달)
os.environ["RATE_LIMIT_ANALYZE"] = "3/minute"
os.environ["RATE_LIMIT_SEARCH"] = "3/minute"

# config 는 다른 테스트(e.g. test_crud_stale)에 의해 이미 import 된 상태일 수 있음.
# 환경변수 재적용을 위해 강제 reload → 이어서 main 도 재수입해 @limiter.limit 가
# 새 리밋 문자열로 다시 등록되도록 한다.
import importlib  # noqa: E402
if "config" in sys.modules:
    importlib.reload(sys.modules["config"])
else:
    import config  # noqa: F401
if "main" in sys.modules:
    del sys.modules["main"]


def _fake_llm_result():
    """analyze_novelty 가 반환할 최소 유효 dict."""
    return {
        "patent_title": "테스트",
        "summary": "테스트 요약",
        "prior_art_comparison": [],
        "five_aspects": {
            "innovation_point": "a",
            "implementation": "b",
            "marketability": "c",
            "design_around": "d",
            "registrability": "e",
        },
        "novelty_score": 50,
        "novelty_reason": "테스트",
        "risk_level": "중간",
        "risk_reason": "테스트",
        "recommendation": "테스트",
    }


@pytest.fixture
def client(monkeypatch):
    """TestClient + LLM mock + limiter 저장소 초기화."""
    import llm as llm_mod
    import main

    monkeypatch.setattr(llm_mod, "analyze_novelty", lambda *a, **k: _fake_llm_result())

    # 다른 테스트가 limiter 스토리지에 남긴 카운터를 초기화 (moving-window 안에 있으면 즉시 429)
    try:
        main.limiter.reset()
    except Exception:
        pass

    return TestClient(main.app)


def test_analyze_rate_limit_triggers_429(client):
    """3/minute 설정 → 4번째 요청에서 429 + Retry-After 헤더."""
    body = {"user_idea": "테스트 아이디어", "patents": []}

    statuses = []
    last_resp = None
    for _ in range(4):
        last_resp = client.post("/analyze", json=body)
        statuses.append(last_resp.status_code)

    # 앞 3건은 200, 4번째는 429
    assert statuses[:3] == [200, 200, 200], f"예상과 다름: {statuses}"
    assert statuses[3] == 429, f"4번째 요청이 429가 아님: {statuses}"
    # slowapi 기본 핸들러는 Retry-After 헤더를 포함함
    assert "retry-after" in {k.lower() for k in last_resp.headers.keys()}


def test_analyze_rate_limit_body_has_detail(client):
    """429 응답 본문에 에러 메시지가 포함되는지 (slowapi 기본 포맷)."""
    body = {"user_idea": "테스트", "patents": []}
    for _ in range(3):
        client.post("/analyze", json=body)
    resp = client.post("/analyze", json=body)
    assert resp.status_code == 429
    data = resp.json()
    # slowapi 기본 응답: {"error": "Rate limit exceeded: ..."}
    assert "error" in data or "detail" in data


def test_analyze_under_limit_succeeds(client):
    """리밋 이내(3회)에서는 모두 200."""
    body = {"user_idea": "테스트", "patents": []}
    for i in range(3):
        resp = client.post("/analyze", json=body)
        assert resp.status_code == 200, f"{i+1}번째 요청 실패: {resp.status_code}"

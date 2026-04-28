# Phase 2-A.1: /trend 빈 결과 캐시 저장 스킵 검증
#
# 배경: fetch_trend_data_from_kipris 는 KIPRIS 장애 시 예외를 swallow 하고
# 빈 dict ({"trend_data": [], "is_truncated": False}) 를 반환한다. 이전 구현에서는
# 빈 dict 가 _trend_cache 에 저장되어 _CACHE_MAX(50) 동안 영구 lock-in 됐다.
# 본 fix 는 /trend 핸들러의 _build closure 에서 빈 trend_data 감지 시 None 을
# 반환해 헬퍼의 캐시 저장 분기를 회피한다 (helper line 152-153).
#
# 4개 시나리오:
#   1. test_trend_empty_result_skips_cache    — 빈 결과 1회차 → _trend_cache 미저장
#   2. test_trend_empty_then_recovery         — 1차 빈 → 2차 정상 → lock-in 회피
#   3. test_trend_normal_caches               — 정상 결과는 기존대로 캐시 (회귀 가드)
#   4. test_trend_is_truncated_only_no_data   — trend_data=[] + is_truncated=True 엣지
#
# 기존 test_trend_cache_concurrency.py (5건) 는 헬퍼 단위 테스트로 본 변경에
# 영향 받지 않음 (영향 분석은 STEP 2 보고 참고).
#
# 실행:
#   python -m pytest backend/tests/test_trend_empty_skip.py -v

import os
import sys

import pytest
from fastapi.testclient import TestClient

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")
# 다른 테스트의 타이트한 레이트 리밋이 오염되지 않도록 기본값 (60/minute) 보다 높게 설정
os.environ["RATE_LIMIT_TREND"] = "100/minute"


def _reload_app():
    """환경변수 변경 후 main/config 를 깨끗이 다시 로드.

    재import 시 _trend_cache / _trend_key_locks 는 빈 dict 로 초기화 → 테스트 격리.
    """
    for mod in ("config", "main"):
        if mod in sys.modules:
            del sys.modules[mod]
    import main  # noqa: F401
    return sys.modules["main"]


def test_trend_empty_result_skips_cache(monkeypatch):
    """1회차 빈 결과 → _trend_cache 에 entry 미저장.

    Phase 2-A.1 핵심 가드 — 빈 trend_data 가 캐시되면 _CACHE_MAX 동안 stale lock-in.
    """
    main = _reload_app()
    monkeypatch.setattr(
        main,
        "fetch_trend_data_from_kipris",
        lambda query, max_count=500: {"trend_data": [], "is_truncated": False},
    )

    client = TestClient(main.app)
    resp = client.get("/trend", params={"query": "__phase2a1_empty__"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["trend_data"] == []
    assert body["is_truncated"] is False
    # 핵심 가드: 캐시에 entry 없어야 함 (lock-in 방지)
    assert "__phase2a1_empty__" not in main._trend_cache


def test_trend_empty_then_recovery(monkeypatch):
    """1차 빈 → 2차 정상 → 정상 결과 반환 (lock-in 회피).

    1차 호출이 빈 결과로 캐시되면 2차도 빈 결과 반환되는 회귀를 차단.
    KIPRIS 가 2회 호출되어야 정상 (1차에서 캐시 미저장 확인).
    """
    main = _reload_app()

    call_count = {"n": 0}

    def flaky_fetch(query, max_count=500):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"trend_data": [], "is_truncated": False}
        return {
            "trend_data": [{"year": "2024", "count": 10}],
            "is_truncated": False,
        }

    monkeypatch.setattr(main, "fetch_trend_data_from_kipris", flaky_fetch)

    client = TestClient(main.app)

    # 1차: 빈 결과
    r1 = client.get("/trend", params={"query": "__phase2a1_recovery__"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["trend_data"] == []

    # 2차: KIPRIS 재호출 → 정상 결과 반환
    r2 = client.get("/trend", params={"query": "__phase2a1_recovery__"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["trend_data"] == [{"year": "2024", "count": 10}]
    # KIPRIS 2회 호출 확인 — 1차에서 캐시 안 됐다는 직접 증거
    assert call_count["n"] == 2


def test_trend_normal_caches(monkeypatch):
    """정상 결과는 기존대로 캐시 (회귀 가드 — 1-G.1 동작 보존).

    2차 호출 시 KIPRIS 재호출 없이 캐시 hit 검증.
    """
    main = _reload_app()

    call_count = {"n": 0}

    def normal_fetch(query, max_count=500):
        call_count["n"] += 1
        return {
            "trend_data": [
                {"year": "2023", "count": 5},
                {"year": "2024", "count": 8},
            ],
            "is_truncated": False,
        }

    monkeypatch.setattr(main, "fetch_trend_data_from_kipris", normal_fetch)

    client = TestClient(main.app)

    # 1차: KIPRIS 호출 → 캐시 저장
    r1 = client.get("/trend", params={"query": "__phase2a1_normal__"})
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["trend_data"]) == 2
    assert "__phase2a1_normal__" in main._trend_cache

    # 2차: 캐시 hit, KIPRIS 미호출
    r2 = client.get("/trend", params={"query": "__phase2a1_normal__"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["trend_data"] == r1.json()["trend_data"]
    assert call_count["n"] == 1


def test_trend_is_truncated_only_no_data(monkeypatch):
    """엣지 케이스: trend_data=[] + is_truncated=True → 캐시 저장 스킵.

    페이지네이션 한계에 도달했으나 결과 0건인 경우. is_truncated=True 라도
    trend_data 가 비면 lock-in 위험은 동일 → 캐시 스킵.

    참고: 헬퍼가 None 반환 시 핸들러 line 421-423 의 default 분기로 떨어져
    응답의 is_truncated 는 False (default) — 빈 결과의 stale 메타정보 전달 회피.
    """
    main = _reload_app()
    monkeypatch.setattr(
        main,
        "fetch_trend_data_from_kipris",
        lambda query, max_count=500: {"trend_data": [], "is_truncated": True},
    )

    client = TestClient(main.app)
    resp = client.get("/trend", params={"query": "__phase2a1_truncated_empty__"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["trend_data"] == []
    # default 분기 통과 — 원본 is_truncated=True 가 아닌 default False 반환
    assert body["is_truncated"] is False
    assert "__phase2a1_truncated_empty__" not in main._trend_cache

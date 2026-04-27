# Phase 1-G.1: _trend_cache 동시성 락 테스트
#
# 검증 대상: main._get_or_build_trend_cache
#   - per-key threading.Lock 으로 같은 query 동시 요청 시 build_fn 1회만 호출
#   - 다른 query 동시 요청 시 build_fn 병렬 실행 허용
#   - build_fn 예외 시 캐시 미저장, 다음 요청 재시도 가능 (방어 가드)
#   - 캐시 hit 경로에서 build_fn 호출 없음
#   - build_fn None 반환 시 캐시 미저장 (방어 가드)
#
# 1-G test_faiss_cache_concurrency.py 와 형태 대칭 — 차이는 헬퍼 이름과 캐시 dict 만.
#
# 실행:
#   python -m pytest backend/tests/test_trend_cache_concurrency.py -v

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")
os.environ.setdefault("USE_MOCK", "false")


@pytest.fixture
def main_module():
    """main 을 깨끗이 reload — 다른 테스트의 레이트 리밋/환경변수 오염 차단.
    각 테스트 시작 시 _trend_cache / _trend_key_locks 모두 비운다.
    """
    if "main" in sys.modules:
        del sys.modules["main"]
    import main  # noqa: F401
    m = sys.modules["main"]

    m._trend_cache.clear()
    with m._trend_cache_guard:
        m._trend_key_locks.clear()
    yield m
    m._trend_cache.clear()
    with m._trend_cache_guard:
        m._trend_key_locks.clear()


def _fake_trend_result(tag: str) -> dict:
    """trend 빌드 결과 모방 — {"trend_data": [...], "is_truncated": bool}."""
    return {
        "trend_data": [{"year": "2024", "count": 1, "tag": tag}],
        "is_truncated": False,
    }


def test_same_key_concurrent_requests_build_once(main_module):
    """같은 query 로 N개 동시 요청 → build_fn 정확히 1회 호출."""
    N = 10
    call_count = 0
    lock_for_counter = threading.Lock()
    # 빌드가 충분히 오래 걸려야 동시 요청들이 겹침. 0.3s 로 설정.
    BUILD_SLEEP = 0.3

    def slow_build():
        nonlocal call_count
        with lock_for_counter:
            call_count += 1
        time.sleep(BUILD_SLEEP)
        return _fake_trend_result("shared")

    def worker():
        return main_module._get_or_build_trend_cache("same-query", slow_build)

    results = []
    with ThreadPoolExecutor(max_workers=N) as pool:
        futures = [pool.submit(worker) for _ in range(N)]
        for f in as_completed(futures):
            results.append(f.result())

    assert call_count == 1, f"build_fn 호출 {call_count}회 (기대: 1)"
    # 모든 스레드가 동일 결과 받음
    assert all(r == _fake_trend_result("shared") for r in results)
    # 캐시 저장 확인
    assert main_module._trend_cache["same-query"] == _fake_trend_result("shared")


def test_different_keys_build_in_parallel(main_module):
    """다른 query 2개 동시 요청 → build_fn 병렬 실행 (per-key lock 이므로 serialize 아님).

    검증법: 빌드 시작/종료 timestamp 를 기록해 overlap 이 있는지 확인.
    만약 전역 락이면 overlap=0, per-key 락이면 overlap>0.
    """
    BUILD_SLEEP = 0.3
    timestamps: dict[str, dict] = {}
    ts_lock = threading.Lock()

    def make_build(tag: str):
        def build():
            with ts_lock:
                timestamps[tag] = {"start": time.monotonic()}
            time.sleep(BUILD_SLEEP)
            with ts_lock:
                timestamps[tag]["end"] = time.monotonic()
            return _fake_trend_result(tag)
        return build

    def worker(tag: str):
        return main_module._get_or_build_trend_cache(f"query-{tag}", make_build(tag))

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(worker, "A")
        f2 = pool.submit(worker, "B")
        r1, r2 = f1.result(), f2.result()

    assert r1 == _fake_trend_result("A")
    assert r2 == _fake_trend_result("B")

    a = timestamps["A"]
    b = timestamps["B"]
    # overlap = min(end) - max(start) > 0 이면 겹침
    overlap = min(a["end"], b["end"]) - max(a["start"], b["start"])
    assert overlap > 0, (
        f"다른 key 가 직렬화됨 (overlap={overlap:.3f}s). "
        f"per-key lock 이 per-query 로 분리되지 않았을 가능성."
    )


def test_build_failure_does_not_poison_cache(main_module):
    """헬퍼의 방어적 가드 동작 검증.

    현 fetch_trend_data_from_kipris 는 예외 swallow + 항상 dict 반환이라 이 경로는
    실제 호출 시 도달 불가. mock 으로 build_fn 동작 강제하여 헬퍼 단위 검증.
    fetch_trend 정책 변경 시 회귀 가드 역할.
    """
    attempts = {"count": 0}

    def failing_build():
        attempts["count"] += 1
        raise RuntimeError("simulated KIPRIS timeout")

    # 첫 요청 — 예외 전파
    with pytest.raises(RuntimeError, match="simulated KIPRIS timeout"):
        main_module._get_or_build_trend_cache("will-fail", failing_build)

    # 캐시에 실패값 저장 안 됨
    assert "will-fail" not in main_module._trend_cache

    # 다음 요청은 다시 build_fn 호출됨 (재시도 가능)
    def succeeding_build():
        attempts["count"] += 1
        return _fake_trend_result("recovered")

    result = main_module._get_or_build_trend_cache("will-fail", succeeding_build)
    assert result == _fake_trend_result("recovered")
    assert attempts["count"] == 2
    assert main_module._trend_cache["will-fail"] == _fake_trend_result("recovered")


def test_cache_hit_skips_build(main_module):
    """이미 캐시에 있는 query 는 build_fn 호출 없이 바로 반환."""
    main_module._trend_cache["preloaded"] = _fake_trend_result("preloaded")

    build_fn = MagicMock()
    result = main_module._get_or_build_trend_cache("preloaded", build_fn)

    assert result == _fake_trend_result("preloaded")
    build_fn.assert_not_called()


def test_build_returning_none_is_not_cached(main_module):
    """헬퍼의 방어적 가드 동작 검증.

    현 fetch_trend_data_from_kipris 는 예외 swallow + 항상 dict 반환이라 이 경로는
    실제 호출 시 도달 불가. mock 으로 build_fn 동작 강제하여 헬퍼 단위 검증.
    fetch_trend 정책 변경 시 회귀 가드 역할.
    """
    calls = {"count": 0}

    def empty_build():
        calls["count"] += 1
        return None

    r1 = main_module._get_or_build_trend_cache("empty-trend", empty_build)
    r2 = main_module._get_or_build_trend_cache("empty-trend", empty_build)

    assert r1 is None
    assert r2 is None
    assert "empty-trend" not in main_module._trend_cache
    # None 결과도 캐시되지 않으므로 재시도 시 다시 호출
    assert calls["count"] == 2

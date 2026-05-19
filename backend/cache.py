"""인메모리 캐시 + 빌드 직렬화 (Phase 3-A.1 분리).

main.py 에서 분리한 모듈. FAISS 인덱스 캐시와 트렌드 캐시 그리고 각각의
동시성 보호 (guard lock + per-key lock) 를 모아둔다.

설계 원칙:
  - dict 자체는 모듈 전역 — 같은 프로세스 안에서 단일 인스턴스 유지.
  - 락은 build 직렬화 용도 (캐시 read 는 락 없이 1차 체크).
  - 빌드 실패 / 빈 결과 시 캐시 저장 스킵 (stale lock-in 방지).
"""

import logging
import threading
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)


# 메모리 캐시 — 동일 쿼리 재요청 시 API 재호출 방지 (최대 50개, 초과 시 오래된 항목 삭제)
_CACHE_MAX = 50
_faiss_cache: dict = {}  # { query: (index, chunks) }
_trend_cache: dict = {}  # { query: { trend_data, is_truncated } }

# Phase 1-G: _faiss_cache 동시성 보호 (per-key threading.Lock + guard lock).
# FastAPI sync handler 는 anyio 스레드풀에서 실행되므로 threading primitive 를 사용한다.
# _faiss_cache_guard : _faiss_key_locks dict 자체를 보호하는 가드 락
# _faiss_key_locks   : 쿼리별 빌드 직렬화용 락 (같은 query 는 한 번만 빌드)
# 락은 재사용 — 빌드 완료 후에도 제거하지 않음. _CACHE_MAX=50 수준이라 누적돼도
# 메모리 영향 미미, 제거 시 race 여지만 늘어남. 의도된 결정.
_faiss_cache_guard: threading.Lock = threading.Lock()
_faiss_key_locks: dict[str, threading.Lock] = {}


def _cache_put(cache: dict, key: str, value):
    """캐시에 항목 추가. 최대 크기 초과 시 가장 오래된 항목 삭제."""
    if key not in cache and len(cache) >= _CACHE_MAX:
        oldest = next(iter(cache))
        del cache[oldest]
    cache[key] = value


def _get_or_build_faiss_index(
    query: str,
    build_fn: Callable[[], Optional[Tuple]],
) -> Optional[Tuple]:
    """_faiss_cache 에서 (index, chunks) 를 조회하거나, 없으면 락을 잡고 빌드한다.

    Double-checked locking 패턴:
      1) lock 없이 1차 체크 (hot path, 99%)
      2) 가드 락으로 key_locks dict 접근 보호, per-key 락 획득/생성
      3) per-key 락 안에서 2차 체크 — 대기 중 다른 스레드가 빌드했을 가능성
      4) build_fn() 호출 후 성공 시에만 캐시에 저장

    build_fn 규약:
      - 반환값: (index, chunks) 튜플 또는 None
      - None  → 빌드 대상 없음 (e.g. 청킹 결과 0건). 캐시 저장 안 함, 호출자에게 None 전달.
      - 예외  → 그대로 전파. 캐시에 실패값 저장 안 함. 다음 요청은 재시도 가능.
    """
    # 1차 체크 — 빠른 경로
    cached = _faiss_cache.get(query)
    if cached is not None:
        return cached

    # 가드 락으로 key_locks dict 보호 (짧게 잡고 놔줌)
    with _faiss_cache_guard:
        key_lock = _faiss_key_locks.get(query)
        if key_lock is None:
            key_lock = threading.Lock()
            _faiss_key_locks[query] = key_lock

    # per-key 락 — 같은 쿼리로 들어온 동시 요청은 여기서 직렬화
    with key_lock:
        # 2차 체크 — 대기 중 다른 스레드가 빌드 완료했을 수 있음
        cached = _faiss_cache.get(query)
        if cached is not None:
            return cached

        # 빌드 (예외 발생 시 그대로 전파 — 캐시에 실패값 저장 안 함)
        result = build_fn()
        if result is None:
            # 빌드 대상 없음 (chunks empty 등) — 캐시 저장 안 함
            return None

        _cache_put(_faiss_cache, query, result)
        return result


# Phase 1-G.1: _trend_cache 동시성 보호 (per-key threading.Lock + guard lock).
# 1-G 의 _faiss_cache 패턴을 trend 캐시에 동일 적용. guard / key_locks 는
# faiss 와 별도 — 같은 query 가 두 캐시에 존재할 때 cross-cache 직렬화 방지.
# 락 누적 정책 / _CACHE_MAX 근거는 _faiss_key_locks 주석과 동일.
_trend_cache_guard: threading.Lock = threading.Lock()
_trend_key_locks: dict[str, threading.Lock] = {}


def _get_or_build_trend_cache(
    query: str,
    build_fn: Callable[[], Optional[dict]],
) -> Optional[dict]:
    """_trend_cache 에서 trend dict 를 조회하거나, 없으면 락을 잡고 빌드한다.

    Double-checked locking 패턴 — _get_or_build_faiss_index 와 동형.

    build_fn 규약:
      - 반환값: dict ({"trend_data": [...], "is_truncated": bool}) 또는 None
      - None  → 캐시 저장 안 함, 호출자에게 None 전달.
      - 예외  → 그대로 전파, 캐시에 실패값 저장 안 함, 다음 요청 재시도 가능.

    실측: 현 build_fn = fetch_trend_data_from_kipris 는 예외 swallow + 항상 dict
    반환이라 None / 예외 분기는 도달 불가. 시그니처는 1-G 와 일치시킴 (방어 가드).
    """
    # 1차 체크 — 빠른 경로
    cached = _trend_cache.get(query)
    if cached is not None:
        logger.info("Trend cache hit: %s", query)
        return cached

    # 가드 락으로 key_locks dict 보호 (짧게 잡고 놔줌)
    with _trend_cache_guard:
        key_lock = _trend_key_locks.get(query)
        if key_lock is None:
            key_lock = threading.Lock()
            _trend_key_locks[query] = key_lock

    # per-key 락 — 같은 쿼리로 들어온 동시 요청은 여기서 직렬화
    with key_lock:
        # 2차 체크 — 대기 중 다른 스레드가 빌드 완료했을 수 있음
        cached = _trend_cache.get(query)
        if cached is not None:
            logger.info("Trend cache hit: %s", query)
            return cached

        # 빌드 (예외 발생 시 그대로 전파 — 캐시에 실패값 저장 안 함)
        logger.info("Trend cache miss. Fetching from KIPRIS: %s", query)
        result = build_fn()
        if result is None:
            return None

        _cache_put(_trend_cache, query, result)
        return result

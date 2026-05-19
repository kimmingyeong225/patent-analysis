"""SlowAPI Limiter 인스턴스 (Phase 3-A.1 분리).

main.py 에서 분리한 모듈. 레이트 리밋은 IP 기준이며, 엔드포인트별 한도는
config.RATE_LIMIT_* env 로 오버라이드 가능.

옵션:
  - key_func=get_remote_address : 클라이언트 IP 기준 카운팅
  - headers_enabled=True : 429 응답에 Retry-After + X-RateLimit-* 헤더 주입
    (클라이언트 backoff 용)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)

import logging
import os
from dotenv import load_dotenv

# .env 파일에서 환경변수를 로드합니다.
load_dotenv()

# 보안을 위해 API 키가 코드에 노출되지 않도록 변경
KIPRIS_API_KEY = os.getenv("KIPRIS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 환경별 분리를 위해 env로 분리. 미지정 시 기존 경로 유지.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./patents.db")

# CORS 허용 오리진: 쉼표 구분 리스트. 기본 "*" (개발 편의).
# 배포 시 CORS_ORIGINS="https://app.example.com,https://admin.example.com" 형태로 제한.
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
] or ["*"]


def log_missing_env() -> list[str]:
    """필수 API 키 누락 시 경고 로깅. 실행은 계속(mock/fallback 경로 있으므로)."""
    logger = logging.getLogger(__name__)
    missing = [name for name in ("KIPRIS_API_KEY", "OPENAI_API_KEY") if not os.getenv(name)]
    if missing:
        logger.warning(
            "누락된 환경변수: %s — .env 파일 또는 시스템 env 확인 필요 (mock/fallback 경로로 계속 동작)",
            ", ".join(missing),
        )
    return missing

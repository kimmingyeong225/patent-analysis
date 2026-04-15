import os
from dotenv import load_dotenv

# .env 파일에서 환경변수를 로드합니다.
load_dotenv()

# 보안을 위해 API 키가 코드에 노출되지 않도록 변경
KIPRIS_API_KEY = os.getenv("KIPRIS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 추가적으로 환경설정이 필요하면 이 곳에 변수 추가
DATABASE_URL = "sqlite:///./patents.db"

import requests

BACKEND_URL = "http://127.0.0.1:8000"


def analyze_novelty(user_idea: str, patents: list, model: str = "gpt-4o") -> dict:
    """
    백엔드 /analyze 엔드포인트를 호출하여 신규성 분석 결과를 반환합니다.
    LLM 로직은 backend/llm.py 에서 실행됩니다.
    """
    try:
        res = requests.post(
            f"{BACKEND_URL}/analyze",
            json={"user_idea": user_idea, "patents": patents},
            timeout=60
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.ConnectionError:
        return {"error": "백엔드 서버에 연결할 수 없습니다.", "raw": ""}
    except Exception as e:
        return {"error": str(e), "raw": ""}

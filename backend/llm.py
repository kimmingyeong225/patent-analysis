import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 시스템 프롬프트 — 역할 정의 + 환각 방지 가드레일
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT = """당신은 10년 경력의 한국 변리사이자 특허 신규성 분석 전문가입니다.

[핵심 규칙 — 반드시 지켜야 합니다]
1. 오직 아래 제공된 선행 특허 데이터만 근거로 사용하세요.
2. 제공되지 않은 특허, 기술, 논문을 언급하지 마세요.
3. 데이터에 없는 내용은 "제공된 데이터에서 확인 불가"라고 명시하세요.
4. 추측이 필요한 경우 반드시 "추정:" 접두어를 붙이세요.
5. 모든 분석은 구체적 근거(어떤 특허의 어떤 부분)를 함께 제시하세요."""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용자 프롬프트 v2 — 선행특허별 비교 + 5가지 관점 분석
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOVELTY_ANALYSIS_PROMPT_V2 = """아래 사용자 아이디어와 유사 선행 특허들을 비교 분석하세요.

[사용자 아이디어]
{user_idea}

[유사 선행 특허 목록]
{patent_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
아래 JSON 형식으로만 응답하세요. JSON 외 다른 텍스트는 절대 출력하지 마세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "patent_title": "사용자 아이디어에 적합한 공식 특허 명칭 제안",
  "summary": "사용자 아이디어를 3문장으로 요약",

  "prior_art_comparison": [
    {{
      "patent_id": "선행특허 출원번호",
      "title": "선행특허 제목",
      "overlap": "사용자 아이디어와 겹치는 기술 요소 설명",
      "difference": "사용자 아이디어만의 차별점 설명",
      "threat_level": "높음 또는 중간 또는 낮음"
    }}
  ],

  "five_aspects": {{
    "innovation_point": "(3문장 이상, 문장마다 줄바꿈) 혁신 포인트 — 기존 선행특허 대비 기술적으로 새로운 점.\\n반드시 근거가 되는 선행특허 출원번호를 명시.\\n어떤 구성요소가 새로운지 구체적으로 서술.",
    "implementation": "(3문장 이상, 문장마다 줄바꿈) 구현 방법 — 핵심 기술 구성요소를 항목별로 나누어 서술.\\n각 구성요소의 역할과 기술적 난이도를 포함.",
    "marketability": "(3문장 이상, 문장마다 줄바꿈) 시장성 — 선행특허 출원인별 동향 분석.\\n시장 관심도와 경쟁 강도.\\n사업화 가능성 판단.",
    "design_around": "(3문장 이상, 문장마다 줄바꿈) 회피 설계 — 위협도 높은 선행특허 명시.\\n침해를 피하기 위한 구체적 설계 변경점.\\n대안 기술 제시.",
    "registrability": "(3문장 이상, 문장마다 줄바꿈) 등록 가능성 — 신규성 판단.\\n진보성 판단.\\n보정이 필요한 청구항 방향 제시."
  }},

  "novelty_score": "0~100 사이 정수",
  "novelty_reason": "점수 산정의 구체적 근거 (어떤 선행특허와 어떤 부분이 겹치거나 다른지)",
  "risk_level": "낮음 또는 중간 또는 높음",
  "risk_reason": "침해 리스크의 구체적 근거",

  "recommendation": "출원 전략에 대한 최종 조언 (2~3문장)"
}}"""


def _build_patent_summary(patents: list) -> str:
    """검색 결과 리스트를 프롬프트용 텍스트로 변환"""
    lines = []
    for p in patents:
        pub = p["공개등록공보"]
        status = p["법적상태"]
        ipc_codes = ", ".join([c["code"] for c in p.get("분류코드", {}).get("ipc", [])])
        claims_text = "\n    ".join(pub.get("claims", []))

        lines.append(
            f"── 선행특허 {p['rank']}위 (유사도: {p['similarity_score']}) ──\n"
            f"  출원번호: {pub.get('application_number', 'N/A')}\n"
            f"  제목: {pub['title']}\n"
            f"  출원인: {pub['applicant']}\n"
            f"  발명자: {pub.get('inventor', 'N/A')}\n"
            f"  출원일: {pub.get('application_date', 'N/A')}\n"
            f"  법적상태: {status.get('status', 'N/A')}\n"
            f"  IPC분류: {ipc_codes or 'N/A'}\n"
            f"  초록: {pub['abstract']}\n"
            f"  청구항:\n    {claims_text if claims_text.strip() else '청구항 정보 없음'}\n"
        )
    return "\n".join(lines)


def analyze_novelty(user_idea: str, patents: list, model: str = "gpt-4o") -> dict:
    """
    사용자 아이디어와 유사 특허 리스트를 받아 GPT로 신규성 분석을 수행합니다.

    Args:
        user_idea: 사용자가 입력한 아이디어 텍스트
        patents:   /search API 응답의 results 리스트
        model:     사용할 OpenAI 모델명

    Returns:
        분석 결과 dict (파싱 실패 시 {"error": ..., "raw": ...} 반환)
    """
    patent_summary = _build_patent_summary(patents)

    user_prompt = NOVELTY_ANALYSIS_PROMPT_V2.format(
        user_idea=user_idea,
        patent_summary=patent_summary,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        raw = response.choices[0].message.content
        clean = raw.replace("```json", "").replace("```", "").strip()
        analysis = json.loads(clean)

        # novelty_score를 int로 정규화 (GPT가 문자열로 반환하는 경우 대비)
        if "novelty_score" in analysis:
            analysis["novelty_score"] = int(analysis["novelty_score"])

        return analysis

    except json.JSONDecodeError:
        return {"error": "JSON 파싱 실패", "raw": raw}
    except Exception as e:
        return {"error": str(e), "raw": ""}

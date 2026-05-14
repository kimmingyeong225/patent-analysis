import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 시스템 프롬프트 — 역할 정의 + 환각 방지 가드레일
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT = """당신은 10년 경력의 한국 변리사이자 특허 신규성 분석 전문가입니다.

[핵심 규칙 — 반드시 지켜야 합니다]
1. 제공된 선행 특허 데이터가 있을 경우, 오직 해당 데이터만 근거로 분석하세요.
2. 제공되지 않은 구체적 특허번호나 문헌을 허위로 만들어내지 마세요.
3. 데이터에 없는 내용은 "제공된 데이터에서 확인 불가"라고 명시하세요.
4. 추측이 필요한 경우 반드시 "추정:" 접두어를 붙이세요.
5. 선행 특허가 없다면, 사용자 아이디어 자체의 기술적 독창성과 잠재적 가치를 분석하세요.
6. novelty_score 는 0~100 정수, threat_level 과 risk_level 은 정확히 "높음" / "중간" / "낮음" 중 하나.
7. 선행 특허가 전혀 없다면 novelty_score를 높게(예: 90~100) 부여하고, prior_art_comparison은 빈 배열([])로 반환하며 risk_level은 "낮음"으로 평가하세요."""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Few-shot 예시 — 출력 일관성 향상 (JSON 스키마·어조·근거 인용 방식)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FEW_SHOT_EXAMPLE_INPUT = """[사용자 아이디어]
자석으로 탈착되는 모듈식 스마트워치 스트랩.

[유사 선행 특허 목록]
── 선행특허 1위 (유사도: 0.82) ──
  출원번호: KR10-2021-0099999
  제목: 자성체 결합 구조를 갖는 시계 스트랩
  출원인: 예시전자
  초록: 스트랩 양단에 자석을 배치하여 공구 없이 교체 가능한 시계 스트랩.
  청구항:
    청구항 1: 자석 결합부를 포함하는 시계 스트랩"""

FEW_SHOT_EXAMPLE_OUTPUT = {
    "patent_title": "자석 탈착식 모듈형 스마트워치 스트랩",
    "summary": "스트랩을 모듈 단위로 자석을 이용해 탈부착한다. 사용자가 공구 없이 구성을 바꿀 수 있다. 선행특허 대비 모듈식 구조가 추가된다.",
    "prior_art_comparison": [
        {
            "patent_id": "KR10-2021-0099999",
            "title": "자성체 결합 구조를 갖는 시계 스트랩",
            "overlap": "스트랩 양단에 자석을 배치해 탈부착하는 구조가 동일.",
            "difference": "본 아이디어는 스트랩을 여러 모듈 단위로 나누어 구성을 조합할 수 있다는 점에서 차별 (선행특허는 단일 스트랩 양단 결합).",
            "threat_level": "중간",
        }
    ],
    "five_aspects": {
        "innovation_point": "선행특허 KR10-2021-0099999 대비 모듈식 분할 구조가 신규.\n사용자가 구성 요소(센서/배터리 모듈 등)를 교체 가능.\n단순 교체가 아닌 기능 조합까지 지원하는 점이 핵심 차별점.",
        "implementation": "자석 결합부는 선행특허 구조를 재사용 가능.\n모듈 간 전기 접점 표준화가 필요(난이도 중).\n모듈 식별용 저전력 통신 프로토콜 설계가 추가 필요.",
        "marketability": "선행특허 출원인은 1개사 — 시장 경쟁 낮음.\n모듈 확장성은 웨어러블 사용자 커스터마이징 트렌드와 부합.\n사업화 가능성 중상.",
        "design_around": "위협도 중간 특허 1건 식별.\n자석 결합부를 슬라이드 락으로 대체하면 회피 가능.\n모듈 간 인터페이스는 별도 IP 확보 가능 영역.",
        "registrability": "신규성: 모듈식 구성은 선행특허에 없음 — 인정 가능.\n진보성: 단순 결합이 아닌 구성 교체성 측면 강조 필요.\n청구항 1을 모듈식 전기 접점 중심으로 보정 권장.",
    },
    "novelty_score": 72,
    "novelty_reason": "핵심 결합부 구조는 KR10-2021-0099999와 겹치나 모듈식 분할·교체 구성은 선행특허에 없음.",
    "risk_level": "중간",
    "risk_reason": "자석 결합부 청구항 일부가 겹칠 가능성 — 설계 변경으로 회피 가능.",
    "recommendation": "청구항을 모듈식 인터페이스와 식별 프로토콜 중심으로 재구성한 뒤 출원 권장. 자석 결합부 단독 청구는 제외.",
}

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
    if not patents:
        return "검색된 유사 선행 특허가 없습니다. 사용자 아이디어 자체의 독창성, 기술적 구현 방법, 시장성을 중심으로 평가하세요."

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


def _clamp_novelty_score(value) -> int:
    """novelty_score 를 0~100 범위의 정수로 정규화.
    비정상값(음수, 초과, 비정수 문자열)은 로깅 후 가까운 경계값으로 clamp.
    """
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        logger.warning("novelty_score 파싱 실패(%r) → 50으로 대체", value)
        return 50
    if score < 0:
        logger.warning("novelty_score<0 (%d) → 0 clamp", score)
        return 0
    if score > 100:
        logger.warning("novelty_score>100 (%d) → 100 clamp", score)
        return 100
    return score


def _call_llm_json(model: str, user_prompt: str) -> str:
    """LLM 호출 후 raw JSON 문자열 반환. 예외는 호출자에서 처리."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            # Few-shot: 입력 형식 → 기대 출력 JSON
            {"role": "user", "content": FEW_SHOT_EXAMPLE_INPUT},
            {"role": "assistant", "content": json.dumps(FEW_SHOT_EXAMPLE_OUTPUT, ensure_ascii=False)},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def analyze_novelty(user_idea: str, patents: list, model: str = "gpt-4o") -> dict:
    """
    사용자 아이디어와 유사 특허 리스트를 받아 GPT로 신규성 분석을 수행합니다.

    Args:
        user_idea: 사용자가 입력한 아이디어 텍스트
        patents:   /search API 응답의 results 리스트
        model:     사용할 OpenAI 모델명

    Returns:
        분석 결과 dict (최종 파싱 실패 시 {"error": ..., "raw": ...} 반환)

    견고성:
      - Few-shot 예시로 JSON 스키마 일관성 강화
      - JSONDecodeError 발생 시 1회 재시도 (프롬프트·temperature 동일)
      - novelty_score 는 0~100 정수로 clamp
    """
    patent_summary = _build_patent_summary(patents)

    user_prompt = NOVELTY_ANALYSIS_PROMPT_V2.format(
        user_idea=user_idea,
        patent_summary=patent_summary,
    )

    raw = ""
    last_parse_err: Exception | None = None

    # JSONDecodeError 에 한해 1회 재시도 (일시적 포맷 일탈 복구용)
    for attempt in range(1, 3):
        try:
            raw = _call_llm_json(model, user_prompt)
            analysis = json.loads(raw)
            break
        except json.JSONDecodeError as e:
            last_parse_err = e
            logger.warning("LLM JSON 파싱 실패(%d/2): %s", attempt, e)
            if attempt == 2:
                return {"error": "JSON 파싱 실패", "raw": raw}
        except Exception as e:
            return {"error": str(e), "raw": raw}
    else:
        return {"error": f"JSON 파싱 실패: {last_parse_err}", "raw": raw}

    if "novelty_score" in analysis:
        analysis["novelty_score"] = _clamp_novelty_score(analysis["novelty_score"])

    return analysis

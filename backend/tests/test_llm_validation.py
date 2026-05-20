# LLM 응답 검증/정규화 가드 (_normalize_risk_level, _validate_and_fill_defaults) 테스트
# - AnalyzeResponse Literal 위반으로 /analyze 500 에러 나던 버그 회귀 방지
# - analyze_novelty 의 빈 patents 조기 방어도 함께 검증 (LLM 호출 skip)
#
# 실행:
#   cd backend && python -m pytest tests/test_llm_validation.py -v

import json
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")

import llm


# ─────────────────────────────────────────────
# _normalize_risk_level — 한국어 Literal + 영문 alias + fallback
# ─────────────────────────────────────────────

def test_risk_level_korean_literal_passthrough():
    assert llm._normalize_risk_level("높음") == "높음"
    assert llm._normalize_risk_level("중간") == "중간"
    assert llm._normalize_risk_level("낮음") == "낮음"


def test_risk_level_strips_whitespace_on_korean():
    assert llm._normalize_risk_level(" 낮음 ") == "낮음"
    assert llm._normalize_risk_level("\t높음\n") == "높음"


def test_risk_level_english_alias_case_insensitive():
    assert llm._normalize_risk_level("Medium") == "중간"
    assert llm._normalize_risk_level("HIGH") == "높음"
    assert llm._normalize_risk_level("low") == "낮음"
    assert llm._normalize_risk_level("Moderate") == "중간"
    assert llm._normalize_risk_level("Severe") == "높음"
    assert llm._normalize_risk_level("minor") == "낮음"
    assert llm._normalize_risk_level("mild") == "낮음"
    assert llm._normalize_risk_level("H") == "높음"
    assert llm._normalize_risk_level("l") == "낮음"


def test_risk_level_unmapped_falls_back_to_medium():
    """매핑에 없는 단어는 '중간' 으로 기본값 + warning."""
    assert llm._normalize_risk_level("critical") == "중간"
    assert llm._normalize_risk_level("제공된 데이터에서 확인 불가") == "중간"


def test_risk_level_non_string_falls_back_to_medium():
    assert llm._normalize_risk_level(None) == "중간"
    assert llm._normalize_risk_level(42) == "중간"
    assert llm._normalize_risk_level({"x": 1}) == "중간"


# ─────────────────────────────────────────────
# _validate_and_fill_defaults — 누락 키 주입 + 타입 정규화
# ─────────────────────────────────────────────

def test_empty_dict_gets_all_required_keys():
    out = llm._validate_and_fill_defaults({})
    missing = llm.REQUIRED_KEYS - out.keys()
    assert not missing, f"누락 키: {missing}"
    # 타입 검증
    assert isinstance(out["novelty_score"], int)
    assert out["risk_level"] in llm.RISK_LEVELS
    assert isinstance(out["prior_art_comparison"], list)
    assert isinstance(out["five_aspects"], dict)
    for k in ("innovation_point", "implementation", "marketability",
              "design_around", "registrability"):
        assert isinstance(out["five_aspects"][k], str)


def test_invalid_risk_level_string_is_corrected():
    out = llm._validate_and_fill_defaults({"risk_level": "invalid"})
    assert out["risk_level"] == "중간"


def test_english_risk_level_is_mapped():
    out = llm._validate_and_fill_defaults({"risk_level": "High"})
    assert out["risk_level"] == "높음"


def test_novelty_score_out_of_range_is_clamped():
    assert llm._validate_and_fill_defaults({"novelty_score": 150})["novelty_score"] == 100
    assert llm._validate_and_fill_defaults({"novelty_score": -5})["novelty_score"] == 0
    # 비정수 문자열은 50으로 대체 (_clamp_novelty_score 규칙)
    assert llm._validate_and_fill_defaults({"novelty_score": "확인 불가"})["novelty_score"] == 50


def test_non_dict_five_aspects_is_replaced():
    out = llm._validate_and_fill_defaults({"five_aspects": "broken"})
    assert isinstance(out["five_aspects"], dict)
    assert set(out["five_aspects"].keys()) == {
        "innovation_point", "implementation", "marketability",
        "design_around", "registrability",
    }


def test_partial_five_aspects_fills_missing_inner_keys():
    out = llm._validate_and_fill_defaults({
        "five_aspects": {"innovation_point": "ok"},  # 나머지 4개 누락
    })
    assert out["five_aspects"]["innovation_point"] == "ok"
    for k in ("implementation", "marketability", "design_around", "registrability"):
        assert out["five_aspects"][k] == "분석 데이터 없음"


def test_non_string_five_aspect_value_replaced():
    out = llm._validate_and_fill_defaults({
        "five_aspects": {"innovation_point": 123},
    })
    assert out["five_aspects"]["innovation_point"] == "분석 데이터 없음"


def test_non_list_prior_art_comparison_replaced():
    out = llm._validate_and_fill_defaults({"prior_art_comparison": "not a list"})
    assert out["prior_art_comparison"] == []


def test_non_dict_analysis_entirely_defaulted():
    """LLM 이 dict 가 아닌 값을 반환한 극단 케이스."""
    out = llm._validate_and_fill_defaults(None)
    assert isinstance(out, dict)
    assert llm.REQUIRED_KEYS <= out.keys()


def test_realistic_buggy_llm_response_is_corrected():
    """실제 버그 재현: LLM 이 enum 필드까지 문자열로 채운 케이스."""
    buggy = {
        "patent_title": "제공된 데이터에서 확인 불가",
        "summary": "제공된 데이터에서 확인 불가",
        "prior_art_comparison": [],
        "five_aspects": {
            "innovation_point": "제공된 데이터에서 확인 불가",
            "implementation": "제공된 데이터에서 확인 불가",
            "marketability": "제공된 데이터에서 확인 불가",
            "design_around": "제공된 데이터에서 확인 불가",
            "registrability": "제공된 데이터에서 확인 불가",
        },
        "novelty_score": "제공된 데이터에서 확인 불가",
        "novelty_reason": "제공된 데이터에서 확인 불가",
        "risk_level": "제공된 데이터에서 확인 불가",  # 이게 Literal 위반의 원인
        "risk_reason": "제공된 데이터에서 확인 불가",
        "recommendation": "제공된 데이터에서 확인 불가",
    }
    out = llm._validate_and_fill_defaults(buggy)
    # Pydantic AnalyzeResponse 가 통과할 수 있는 상태인지 검증
    assert out["risk_level"] in llm.RISK_LEVELS
    assert isinstance(out["novelty_score"], int)
    assert 0 <= out["novelty_score"] <= 100


# ─────────────────────────────────────────────
# analyze_novelty — 빈 patents 조기 방어 (LLM mocked → 호출 여부 검증)
# ─────────────────────────────────────────────

@pytest.fixture
def llm_spy(monkeypatch):
    """_call_llm_json 호출 카운터. 호출되면 예외 — 빈 patents 경로에선 호출 0회여야."""
    calls = {"count": 0}

    def fake_call(model, user_prompt):
        calls["count"] += 1
        # 호출된 경우에만 유효 JSON 반환 (비지 테스트용)
        return json.dumps({
            "patent_title": "정상",
            "summary": "정상",
            "prior_art_comparison": [],
            "five_aspects": {k: "v" for k in (
                "innovation_point", "implementation", "marketability",
                "design_around", "registrability",
            )},
            "novelty_score": 42,
            "novelty_reason": "정상",
            "risk_level": "중간",
            "risk_reason": "정상",
            "recommendation": "정상",
        }, ensure_ascii=False)

    monkeypatch.setattr(llm, "_call_llm_json", fake_call)
    return calls


def test_analyze_novelty_with_empty_list_skips_llm(llm_spy):
    result = llm.analyze_novelty("아이디어", [])
    assert llm_spy["count"] == 0, "빈 리스트인데 LLM 호출됨"
    assert llm.REQUIRED_KEYS <= result.keys()
    assert result["risk_level"] in llm.RISK_LEVELS


def test_analyze_novelty_with_none_patents_skips_llm(llm_spy):
    result = llm.analyze_novelty("아이디어", None)
    assert llm_spy["count"] == 0, "None 입력인데 LLM 호출됨"
    assert llm.REQUIRED_KEYS <= result.keys()
    assert result["risk_level"] in llm.RISK_LEVELS


def test_analyze_novelty_with_empty_dict_skips_llm(llm_spy):
    """dict 도 falsy 면 동일하게 처리 (엄격한 not-patents 판정)."""
    result = llm.analyze_novelty("아이디어", {})
    assert llm_spy["count"] == 0, "빈 dict 인데 LLM 호출됨"
    assert result["risk_level"] in llm.RISK_LEVELS


def test_analyze_novelty_with_real_patents_calls_llm(llm_spy):
    """정상 경로: patents 가 있으면 LLM 호출 1회."""
    patents = [{
        "rank": 1,
        "similarity_score": 0.9,
        "공개등록공보": {
            "application_number": "KR10-2020-0000001",
            "title": "t", "applicant": "a", "inventor": "i",
            "application_date": "20200101",
            "abstract": "abs", "claims": ["c1"],
        },
        "법적상태": {"status": "등록"},
        "분류코드": {"ipc": [{"code": "A01B", "desc": ""}]},
    }]
    result = llm.analyze_novelty("아이디어", patents)
    assert llm_spy["count"] == 1
    assert result["risk_level"] == "중간"
    assert result["novelty_score"] == 42

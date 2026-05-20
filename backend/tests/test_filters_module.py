# Phase 2-A.3: filters.apply_filters 모듈 동작 검증
#
# 배경: main._apply_filters / crud._apply_cache_filters 라인 단위 동일 중복을
# backend/filters.py 단일 모듈로 통합. 본 테스트는 분리 후에도 출원연도 / 법적상태
# 필터가 동일 규칙으로 동작하는지 확인 (라인 단위 본문 이동이라 회귀 위험은 거의 0,
# 단 import path / 모듈 구조 변경 검증 1회 가치).
#
# 3개 시나리오:
#   1. test_year_from_to_filter   — year_from / year_to 범위 통과 / 차단 검증
#   2. test_status_filter         — 법적상태 매칭 / 미매칭 검증
#   3. test_no_filter_passthrough — 필터 미설정 시 원본 그대로 반환
#
# 미러 패턴: test_trend_empty_skip / test_faiss_score_cache_key 정합.
# - 모듈 top-level OPENAI_API_KEY=test-dummy (setdefault) — filters 자체는 OpenAI
#   무관이지만 backend 모듈 reload 안전성 위해 일관 적용.
# - filters 모듈은 schemas 만 의존 (leaf) → _reload_app() 헬퍼 불필요, 직접 import.
# - fixture / parametrize 미사용. 캐시 미경유라 유니크 query 불필요.
#
# 실행:
#   python -m pytest backend/tests/test_filters_module.py -v

import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")

import filters
import schemas


def _make_patent(pid: str, application_date: str = "", status: str = "") -> dict:
    """테스트용 최소 patent dict — apply_filters 가 참조하는 키만 포함."""
    return {
        "공개등록공보": {
            "patent_id": pid,
            "application_date": application_date,
        },
        "법적상태": {
            "status": status,
        },
    }


def test_year_from_to_filter():
    """year_from=2015, year_to=2020 → 2015~2020 만 통과, 외부 차단."""
    patents = [
        _make_patent("P-2010", "20100315"),
        _make_patent("P-2015", "20150601"),
        _make_patent("P-2018", "20180101"),
        _make_patent("P-2020", "20201231"),
        _make_patent("P-2022", "20220715"),
        _make_patent("P-empty", ""),         # 빈 날짜 → 차단
        _make_patent("P-short", "201"),       # 4자 미만 → 차단
        _make_patent("P-bad", "abcd0101"),    # 비숫자 → 차단
    ]
    request = schemas.SearchRequest(query="x", year_from=2015, year_to=2020)
    result = filters.apply_filters(patents, request)

    pids = {p["공개등록공보"]["patent_id"] for p in result}
    assert pids == {"P-2015", "P-2018", "P-2020"}, (
        f"year_from=2015/year_to=2020 통과 항목={pids} (기대: P-2015/P-2018/P-2020)"
    )


def test_status_filter():
    """status='등록' → 법적상태가 정확히 '등록'인 항목만 통과."""
    patents = [
        _make_patent("P1", "20200101", status="등록"),
        _make_patent("P2", "20200101", status="공개"),
        _make_patent("P3", "20200101", status="등록"),
        _make_patent("P4", "20200101", status=""),  # 빈 status → 차단
    ]
    request = schemas.SearchRequest(query="x", status="등록")
    result = filters.apply_filters(patents, request)

    pids = {p["공개등록공보"]["patent_id"] for p in result}
    assert pids == {"P1", "P3"}, (
        f"status=등록 통과 항목={pids} (기대: P1/P3)"
    )


def test_no_filter_passthrough():
    """year_from / year_to / status 모두 미설정 → 원본 리스트 그대로 반환."""
    patents = [
        _make_patent("P1", "20100101", status="등록"),
        _make_patent("P2", "", status=""),
        _make_patent("P3", "20990101", status="공개"),
    ]
    request = schemas.SearchRequest(query="x")  # year_from / year_to / status 미설정
    result = filters.apply_filters(patents, request)

    pids = [p["공개등록공보"]["patent_id"] for p in result]
    assert pids == ["P1", "P2", "P3"], (
        f"필터 미설정 시 원본 순서 유지 실패: {pids}"
    )
    assert len(result) == 3

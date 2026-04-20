# get_cached_search 의 stale 캐시 감지 테스트
# - placeholder claims / 빈 claims 가 섞여 있으면 None 을 반환해 재조회를 유도하는지 검증
# - SearchResult 매핑 회수까지 함께 검증
#
# 실행:
#   cd backend && python -m pytest tests/test_crud_stale.py -v

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# backend 디렉토리 path 추가 (이 파일은 backend/tests/ 에 위치)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import models
import schemas
import crud
from database import Base
from kipris import STALE_CLAIMS_PLACEHOLDER


@pytest.fixture
def session():
    """각 테스트마다 독립된 in-memory SQLite 세션을 제공."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _seed_patent(db, patent_id: str, query: str, claims):
    """최소 구성의 Patent + SearchResult 픽스처."""
    db.add(models.Patent(
        patent_id=patent_id,
        application_number="1020180000001",
        title="테스트 특허",
        applicant="테스트 출원인",
        inventor="테스트 발명자",
        application_date="20180928",
        publication_date="20200101",
        registration_date=None,
        abstract="테스트 초록",
        claims=claims,
        doc_type="공개",
    ))
    db.add(models.SearchResult(
        query=query,
        patent_id=patent_id,
        rank=1,
        similarity_score=0.9,
    ))
    db.commit()


def _default_request(query="테스트 쿼리") -> schemas.SearchRequest:
    return schemas.SearchRequest(query=query, max_results=5)


def test_returns_none_when_claims_is_placeholder(session):
    query = "q_placeholder"
    _seed_patent(session, "P-001", query, [STALE_CLAIMS_PLACEHOLDER])

    result = crud.get_cached_search(session, query, _default_request(query))

    assert result is None
    # SearchResult 매핑이 회수되었는지 확인
    remaining = (
        session.query(models.SearchResult)
        .filter(models.SearchResult.query == query)
        .count()
    )
    assert remaining == 0
    # Patent 원본은 보존
    assert (
        session.query(models.Patent).filter(models.Patent.patent_id == "P-001").count()
        == 1
    )


def test_returns_none_when_claims_is_empty_list(session):
    query = "q_empty"
    _seed_patent(session, "P-002", query, [])

    result = crud.get_cached_search(session, query, _default_request(query))

    assert result is None
    remaining = (
        session.query(models.SearchResult)
        .filter(models.SearchResult.query == query)
        .count()
    )
    assert remaining == 0


def test_returns_none_when_claims_is_null(session):
    query = "q_null"
    _seed_patent(session, "P-003", query, None)

    result = crud.get_cached_search(session, query, _default_request(query))

    assert result is None


def test_returns_items_when_claims_are_real(session):
    query = "q_fresh"
    _seed_patent(
        session,
        "P-004",
        query,
        ["청구항 1. 본체와 이에 결합된 태양광 모듈을 포함하는 스마트 워치."],
    )

    result = crud.get_cached_search(session, query, _default_request(query))

    assert result is not None
    assert len(result) == 1
    assert result[0]["공개등록공보"]["patent_id"] == "P-004"
    assert result[0]["공개등록공보"]["claims"][0].startswith("청구항 1")
    # rank 재부여 확인 (1부터)
    assert result[0]["rank"] == 1


def test_returns_none_when_one_of_many_is_stale(session):
    """상위 max_results 범위 내에 stale 건이 있으면 재조회 — 부분 stale 혼합을 방지."""
    query = "q_mixed"
    # 신선한 건 (rank 1)
    _seed_patent(session, "P-005", query, ["청구항 1. 정상적인 본문"])
    # rank 2에 stale 추가 (max_results=5 범위 내)
    session.add(models.Patent(
        patent_id="P-006",
        application_number="1020180000002",
        title="B",
        applicant="",
        inventor="",
        application_date="20180101",
        publication_date=None,
        registration_date=None,
        abstract="",
        claims=[STALE_CLAIMS_PLACEHOLDER],
        doc_type="공개",
    ))
    session.add(models.SearchResult(
        query=query, patent_id="P-006", rank=2, similarity_score=0.5,
    ))
    session.commit()

    result = crud.get_cached_search(session, query, _default_request(query))

    assert result is None


def test_hybrid_placeholder_beyond_max_results_is_not_stale(session):
    """하이브리드 저장 전략 검증: rank > max_results 범위의 placeholder는 stale 아님.
    상위 max_results 건이 전부 enriched면 정상 캐시 hit으로 처리.
    """
    query = "q_hybrid"
    # rank 1,2,3 (max_results 범위): enriched
    for rank, pid in enumerate(("P-010", "P-011", "P-012"), start=1):
        session.add(models.Patent(
            patent_id=pid,
            application_number=f"102018000010{rank}",
            title=f"T-{pid}",
            applicant="", inventor="",
            application_date="20200101",
            publication_date=None, registration_date=None,
            abstract="",
            claims=[f"청구항 1. 실제 본문 {pid}"],
            doc_type="공개",
        ))
        session.add(models.SearchResult(
            query=query, patent_id=pid, rank=rank, similarity_score=0.9 - rank * 0.05,
        ))
    # rank 4,5 (max_results 범위 초과): placeholder로 저장됨 — 정상 상태
    for rank, pid in enumerate(("P-013", "P-014"), start=4):
        session.add(models.Patent(
            patent_id=pid,
            application_number=f"102018000010{rank}",
            title=f"T-{pid}",
            applicant="", inventor="",
            application_date="20200101",
            publication_date=None, registration_date=None,
            abstract="",
            claims=[STALE_CLAIMS_PLACEHOLDER],
            doc_type="공개",
        ))
        session.add(models.SearchResult(
            query=query, patent_id=pid, rank=rank, similarity_score=0.5,
        ))
    session.commit()

    # max_results=3 으로 요청 — 상위 3건만 검사
    req = schemas.SearchRequest(query=query, max_results=3)
    result = crud.get_cached_search(session, query, req)

    assert result is not None, "하이브리드: 상위 3건 enriched면 정상 캐시로 판정"
    assert len(result) == 3
    for item in result:
        assert not item["공개등록공보"]["claims"][0].startswith(STALE_CLAIMS_PLACEHOLDER[:20])


def test_returns_none_when_query_has_no_cache(session):
    """기존 '캐시 miss' 경로 (rows 자체가 없음) 와 stale 경로의 분기 검증."""
    result = crud.get_cached_search(session, "never_searched", _default_request())
    assert result is None

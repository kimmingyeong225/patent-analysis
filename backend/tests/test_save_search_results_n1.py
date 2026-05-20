# Phase 2-A.4: save_search_results N+1 해소 검증
#
# 배경: 루프 내 4종 query (Patent SELECT / Citation SELECT / LegalStatus SELECT
# + Classification DELETE) 가 N+1 의 본질이었음. 30 patents 시 ~341 queries.
# Phase 2-A.4 fix (옵션 1-β): 루프 외 IN 절 batch SELECT (Patent/Citation/
# LegalStatus) + 루프 외 IN 절 batch DELETE (Classification) + 루프 후
# bulk_insert_mappings(Classification). 30p 시 ~125 queries (63% 절감).
#
# 6개 시나리오:
#   1. test_save_search_results_correctness_5p   — 5p 입력 → DB row 정확
#   2. test_save_search_results_correctness_30p  — 30p 입력 → 동일 정합성, 큰 N 회귀 가드
#   3. test_save_search_results_query_count      — 30p 시 ≤ 130 queries (1-β 기대 ~125 + 안전 마진)
#   4. test_save_search_results_existing_update  — 기존 patents 가 있을 때 UPDATE path 동작
#   5. test_save_search_results_empty            — 빈 results 입력 → 외부 DELETE search_results 1회만 발행
#   6. test_save_search_results_missing_pid      — 일부 항목 patent_id 누락 → continue 분기 + 나머지 정상 저장
#
# 미러 패턴: test_filters_module / test_trend_empty_skip / test_faiss_score_cache_key.
# - sys.path 부트스트랩 + OPENAI_API_KEY=test-dummy setdefault
# - fixture / parametrize 미사용
# - DB 격리: in-memory SQLite engine 자체 생성 + Base.metadata.create_all 로 격리
#   (운영 patents.db 오염 방지). SessionLocal 도 in-memory engine 으로 별도 sessionmaker.
# - 유니크 patent_id prefix: PROBE-N1-* (다른 테스트와 충돌 회피)
#
# 실행:
#   python -m pytest backend/tests/test_save_search_results_n1.py -v

import os
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("OPENAI_API_KEY", "test-dummy")

import models
import crud


def _make_isolated_db():
    """각 테스트마다 in-memory SQLite + 신규 schema → 운영 DB 오염 0."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, Session()


def _make_patent(pid: str, *, ipc_count: int = 2, cpc_count: int = 1) -> dict:
    """테스트용 KIPRIS 응답 형태 dict — save_search_results 가 참조하는 키만 포함."""
    return {
        "공개등록공보": {
            "patent_id": pid,
            "application_number": f"APP-{pid}",
            "title": f"Title {pid}",
            "applicant": f"Applicant {pid}",
            "inventor": f"Inventor {pid}",
            "application_date": "20200101",
            "publication_date": "20200601",
            "registration_date": "20210101",
            "abstract": f"Abstract for {pid}",
            "claims": [f"Claim 1 of {pid}"],
            "doc_type": "P",
        },
        "인용문헌": {
            "cited_by_count": 3,
            "citing_count": 2,
            "cited_patents": ["CITED-A", "CITED-B"],
        },
        "법적상태": {
            "status": "등록",
            "status_code": "R0000",
            "last_event": "등록결정",
            "last_event_date": "20210101",
            "is_alive": True,
        },
        "분류코드": {
            "ipc": [{"code": f"IPC{i}", "desc": f"ipc desc {i}"} for i in range(ipc_count)],
            "cpc": [{"code": f"CPC{i}", "desc": f"cpc desc {i}"} for i in range(cpc_count)],
        },
        "rank": 1,
        "similarity_score": 0.5,
    }


def test_save_search_results_correctness_5p():
    """5 patents → Patent/Citation/LegalStatus 5건 + Classification 5×3 + SearchResult 5건."""
    engine, db = _make_isolated_db()
    try:
        patents = [_make_patent(f"PROBE-N1-{i:04d}") for i in range(5)]
        crud.save_search_results(db, "__phase2a4_n1_correctness_5p__", patents)

        assert db.query(models.Patent).count() == 5
        assert db.query(models.Citation).count() == 5
        assert db.query(models.LegalStatus).count() == 5
        # Classification: 5 patents × (2 ipc + 1 cpc) = 15
        assert db.query(models.Classification).count() == 15
        assert db.query(models.SearchResult).count() == 5

        # patent_id 보존 검증
        saved_pids = {p.patent_id for p in db.query(models.Patent).all()}
        assert saved_pids == {f"PROBE-N1-{i:04d}" for i in range(5)}

        # SearchResult ↔ query 매핑 정확성
        sr_pids = {
            sr.patent_id
            for sr in db.query(models.SearchResult).filter(
                models.SearchResult.query == "__phase2a4_n1_correctness_5p__"
            ).all()
        }
        assert sr_pids == saved_pids
    finally:
        db.close()


def test_save_search_results_correctness_30p():
    """30 patents → 큰 N 회귀 가드, IN 절 + bulk_insert_mappings 정상 동작."""
    engine, db = _make_isolated_db()
    try:
        patents = [_make_patent(f"PROBE-N1-{i:04d}") for i in range(30)]
        crud.save_search_results(db, "__phase2a4_n1_correctness_30p__", patents)

        assert db.query(models.Patent).count() == 30
        assert db.query(models.Citation).count() == 30
        assert db.query(models.LegalStatus).count() == 30
        assert db.query(models.Classification).count() == 90  # 30 × 3
        assert db.query(models.SearchResult).count() == 30

        # bulk_insert_mappings 가 모든 row 를 정확히 삽입했는지 (data integrity)
        ipc_rows = db.query(models.Classification).filter(
            models.Classification.code_type == "ipc"
        ).count()
        cpc_rows = db.query(models.Classification).filter(
            models.Classification.code_type == "cpc"
        ).count()
        assert ipc_rows == 60  # 30 × 2
        assert cpc_rows == 30  # 30 × 1
    finally:
        db.close()


def test_save_search_results_query_count():
    """30 patents 시 ≤ 130 queries (1-β 기대 ~125 + 안전 마진).

    핵심 가드 — 옵션 1-α/β 회귀 시 (e.g., 누군가 IN 절 풀고 다시 N+1 도입) 실패.
    """
    engine, db = _make_isolated_db()

    counter = {"count": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        counter["count"] += 1

    try:
        patents = [_make_patent(f"PROBE-N1-{i:04d}") for i in range(30)]
        counter["count"] = 0
        crud.save_search_results(db, "__phase2a4_n1_query_count__", patents)
        # 1-β 기대치 ~125. 안전 마진 5% → 130 한계.
        # SQLAlchemy 가 bulk_insert_mappings 를 청크별로 발행할 가능성 대비,
        # 실측 후 임계값 미세조정 가능 (현재 보수적으로 130).
        assert counter["count"] <= 130, (
            f"queries={counter['count']} > 130. N+1 회귀 가능성."
        )
    finally:
        db.close()


def test_save_search_results_existing_update():
    """기존 patents 가 있을 때 UPDATE path — 중복 INSERT 안 됨, attribute 갱신."""
    engine, db = _make_isolated_db()
    try:
        # 1차 저장 — 5건 신규 INSERT
        patents_v1 = [_make_patent(f"PROBE-N1-{i:04d}") for i in range(5)]
        crud.save_search_results(db, "__phase2a4_n1_update_v1__", patents_v1)

        assert db.query(models.Patent).count() == 5
        first_titles = {p.patent_id: p.title for p in db.query(models.Patent).all()}

        # 2차 저장 — 동일 patent_id, 다른 title (UPDATE 검증용)
        patents_v2 = [_make_patent(f"PROBE-N1-{i:04d}") for i in range(5)]
        for p in patents_v2:
            p["공개등록공보"]["title"] = f"UPDATED {p['공개등록공보']['patent_id']}"
        crud.save_search_results(db, "__phase2a4_n1_update_v2__", patents_v2)

        # Patent row 수 동일 (중복 INSERT 안 됨)
        assert db.query(models.Patent).count() == 5

        # title 갱신 확인
        updated_titles = {p.patent_id: p.title for p in db.query(models.Patent).all()}
        for pid in first_titles:
            assert updated_titles[pid] == f"UPDATED {pid}", (
                f"{pid}: title={updated_titles[pid]} (기대: UPDATED ...)"
            )

        # SearchResult: 두 query 모두 매핑 존재
        assert db.query(models.SearchResult).filter(
            models.SearchResult.query == "__phase2a4_n1_update_v1__"
        ).count() == 5
        assert db.query(models.SearchResult).filter(
            models.SearchResult.query == "__phase2a4_n1_update_v2__"
        ).count() == 5

        # Classification: DELETE 후 재삽입이라 row 수 그대로 (5×3=15)
        assert db.query(models.Classification).count() == 15
    finally:
        db.close()


def test_save_search_results_empty():
    """빈 results → 외부 DELETE 1회 + commit 만, 예외 없음."""
    engine, db = _make_isolated_db()

    counter = {"count": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        counter["count"] += 1

    try:
        counter["count"] = 0
        crud.save_search_results(db, "__phase2a4_n1_empty__", [])
        # 외부 DELETE search_results 1회 (빈 입력 가드 후 commit). IN 절 호출 0.
        assert counter["count"] <= 2, (
            f"empty 입력 시 queries={counter['count']} (기대: ≤ 2 — 외부 DELETE + commit overhead)"
        )
        # 실제 row 추가 0
        assert db.query(models.Patent).count() == 0
        assert db.query(models.SearchResult).count() == 0
    finally:
        db.close()


def test_save_search_results_missing_pid():
    """일부 항목 patent_id 누락 → 해당 항목 skip + 나머지 정상 저장."""
    engine, db = _make_isolated_db()
    try:
        patents = [
            _make_patent("PROBE-N1-OK1"),
            _make_patent("PROBE-N1-OK2"),
            _make_patent("PROBE-N1-OK3"),
        ]
        # 두 번째 항목은 patent_id 누락 (KIPRIS 응답 비정상 시뮬)
        patents[1]["공개등록공보"]["patent_id"] = None

        crud.save_search_results(db, "__phase2a4_n1_missing_pid__", patents)

        # 정상 2건만 저장 (None 1건 skip)
        saved_pids = {p.patent_id for p in db.query(models.Patent).all()}
        assert saved_pids == {"PROBE-N1-OK1", "PROBE-N1-OK3"}
        assert db.query(models.SearchResult).count() == 2
        # Classification: 2 × 3 = 6 (skip 항목 제외)
        assert db.query(models.Classification).count() == 6
    finally:
        db.close()

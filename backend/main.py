import logging
import os

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# 다른 모듈이 logger를 잡기 전에 루트 로깅 구성을 먼저 적용
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

import models, schemas, crud
import config
from database import engine, get_db, Base
from kipris import fetch_patent_data_from_kipris, fetch_trend_data_from_kipris
from mock_data import MOCK_SEARCH_RESPONSE
import llm

# 메모리 캐시 — 동일 쿼리 재요청 시 API 재호출 방지 (최대 50개, 초과 시 오래된 항목 삭제)
_CACHE_MAX = 50
_faiss_cache: dict = {}  # { query: (index, chunks) }
_trend_cache: dict = {}  # { query: { trend_data, is_truncated } }

def _cache_put(cache: dict, key: str, value):
    """캐시에 항목 추가. 최대 크기 초과 시 가장 오래된 항목 삭제."""
    if key not in cache and len(cache) >= _CACHE_MAX:
        oldest = next(iter(cache))
        del cache[oldest]
    cache[key] = value
# 환경 변수 로드 (.env 파일) — config.py에서도 이미 로드하나 명시성 위해 유지
load_dotenv()
# 필수 env 누락 체크 (경고 레벨 — 실행은 계속)
config.log_missing_env()
# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)
app = FastAPI(title="특허 분석 시스템 API", version="1.0.0")

# 레이트 리밋 — IP 기준. 엔드포인트별 한도는 config.RATE_LIMIT_* env로 오버라이드 가능.
# - headers_enabled=True : 429 응답에 Retry-After + X-RateLimit-* 헤더 주입 (클라이언트 backoff 용)
# - SlowAPIMiddleware : FastAPI 응답이 Response 객체로 완성된 뒤 헤더를 안전하게 추가
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS 설정 — CORS_ORIGINS env로 제어 (기본 "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------- 팀원 작성 부분 (기본 작동 확인용) -----------------
@app.get("/")
def root():
    return {"message": "특허 분석 서버 작동 중!"}
# ---------------------------------------------------------------------
@app.post("/search", response_model=schemas.SearchResponse)
@limiter.limit(config.RATE_LIMIT_SEARCH)
def search_patents(
    request: Request,
    response: Response,
    payload: schemas.SearchRequest,
    db: Session = Depends(get_db),
):
    """
    주어진 쿼리에 대해 KIPRIS API를 검색하고 결과를 반환합니다.

    흐름:
      1) USE_MOCK=true 이면 mock 경로
      2) DB 영구 캐시 조회 (동일 query — 필터는 응답 직전에 후처리)
      3) 캐시 miss → KIPRIS 호출 → FAISS 점수/정렬 → DB 저장(원본) → 필터/limit 후 응답
    """
    query = payload.query

    # 1) USE_MOCK 우선 (DB를 우회)
    if os.getenv("USE_MOCK", "false").lower() == "true":
        logger.info("USE_MOCK=true -> mock 데이터 사용")
        parsed_results = list(MOCK_SEARCH_RESPONSE["results"])
        parsed_results = _apply_filters(parsed_results, payload)
        parsed_results = _apply_faiss_scores(parsed_results, query)
        parsed_results = parsed_results[:payload.max_results]
        for i, p in enumerate(parsed_results):
            p["rank"] = i + 1
        return {"query": query, "cached": False, "results": parsed_results}

    # 2) DB 캐시 조회 (필터/max_results는 캐시 후처리로 적용됨)
    cached = crud.get_cached_search(db, query, payload)
    if cached is not None:
        logger.info("DB cache hit: %s", query)
        return {"query": query, "cached": True, "results": cached}

    # 3) 캐시 miss → KIPRIS 호출
    logger.info("DB cache miss. Fetching from KIPRIS: %s", query)
    fetch_count = max(payload.max_results * 4, 30)
    parsed_results = fetch_patent_data_from_kipris(query, docs_count=fetch_count)
    if not parsed_results:
        logger.warning("KIPRIS 결과 없음 → MOCK_DATA로 폴백")
        parsed_results = list(MOCK_SEARCH_RESPONSE["results"])

    # FAISS 유사도 점수 적용 및 정렬 (DB에는 필터 이전 원본을 저장)
    parsed_results = _apply_faiss_scores(parsed_results, query)

    # DB 영구 저장 — 저장 실패는 응답을 막지 않음 (사용자 요청은 계속 처리)
    try:
        crud.save_search_results(db, query, parsed_results)
    except Exception as e:
        logger.error("DB 저장 실패 (응답은 계속): %s", e)

    # 응답 직전 필터/제한/rank 재부여
    parsed_results = _apply_filters(parsed_results, payload)
    parsed_results = parsed_results[:payload.max_results]
    for i, p in enumerate(parsed_results):
        p["rank"] = i + 1

    return {"query": query, "cached": False, "results": parsed_results}


def _apply_filters(patents: list, request: schemas.SearchRequest) -> list:
    """출원연도 범위, 법적상태 필터를 적용합니다."""
    filtered = patents

    # 출원연도 필터
    if request.year_from or request.year_to:
        def in_year_range(p):
            date = p.get("공개등록공보", {}).get("application_date", "") or ""
            if len(date) < 4:
                return False
            try:
                year = int(date[:4])
            except ValueError:
                return False
            if request.year_from and year < request.year_from:
                return False
            if request.year_to and year > request.year_to:
                return False
            return True
        filtered = [p for p in filtered if in_year_range(p)]

    # 법적상태 필터
    if request.status:
        filtered = [
            p for p in filtered
            if p.get("법적상태", {}).get("status", "") == request.status
        ]

    return filtered
@app.get("/patent/{patent_id}")
def get_patent_detail(patent_id: str, db: Session = Depends(get_db)):
    """
    단일 특허 상세 조회.
    1) /search가 채운 DB 우선 조회
    2) 없으면 mock 데이터에서 폴백 조회
    """
    patent = db.query(models.Patent).filter(models.Patent.patent_id == patent_id).first()
    if patent:
        item = crud.db_row_to_search_result_item(patent)
        return {"patent_id": patent_id, "공개등록공보": item["공개등록공보"]}

    for result in MOCK_SEARCH_RESPONSE["results"]:
        if result["공개등록공보"]["patent_id"] == patent_id:
            return {
                "patent_id": patent_id,
                "공개등록공보": result["공개등록공보"]
            }

    raise HTTPException(status_code=404, detail="Patent not found")

@app.post("/analyze", response_model=schemas.AnalyzeResponse)
@limiter.limit(config.RATE_LIMIT_ANALYZE)
def analyze_patent(request: Request, response: Response, payload: schemas.AnalyzeRequest):
    """
    사용자 아이디어와 유사 특허 리스트를 받아 GPT-4o로 신규성 분석을 수행합니다.
    """
    patents_as_dict = [p.model_dump() for p in payload.patents]
    result = llm.analyze_novelty(payload.user_idea, patents_as_dict)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.get("/trend")
@limiter.limit(config.RATE_LIMIT_TREND)
def get_trend(request: Request, response: Response, query: str):
    """
    키워드별 연도별 출원 트렌드.
    KIPRIS에서 최대 500건을 페이지네이션하여 출원연도별 실제 건수를 집계합니다.
    동일 쿼리는 메모리 캐시를 재사용합니다.
    """
    if query in _trend_cache:
        logger.info("Trend cache hit: %s", query)
        cached = _trend_cache[query]
        return {"query": query, "trend_data": cached["trend_data"], "is_truncated": cached["is_truncated"]}

    logger.info("Trend cache miss. Fetching from KIPRIS: %s", query)
    result = fetch_trend_data_from_kipris(query)
    _cache_put(_trend_cache, query, result)

    return {"query": query, "trend_data": result["trend_data"], "is_truncated": result["is_truncated"]}

# ──────────────── 유사도 검색 엔드포인트 (팀원 2 추가) ────────────────

from embedding import chunk_patents, build_faiss_index, search_similar


def _apply_faiss_scores(patents: list, query: str) -> list:
    """
    KIPRIS 결과에 FAISS 코사인 유사도 점수를 적용합니다.
    특허별로 청크 중 최고 유사도를 대표 점수로 사용하고 내림차순 정렬합니다.
    동일 쿼리는 캐시된 인덱스를 재사용합니다.
    """
    try:
        if query in _faiss_cache:
            index, chunks = _faiss_cache[query]
        else:
            chunks = chunk_patents(patents)
            if not chunks:
                return patents
            index, chunks = build_faiss_index(chunks)
            _cache_put(_faiss_cache, query, (index, chunks))

        chunk_results = search_similar(query, index, chunks, top_k=len(chunks))

        # 특허 ID별 최고 유사도 점수 집계
        best_scores: dict[str, float] = {}
        for r in chunk_results:
            pid = r["patent_id"]
            if pid not in best_scores or r["similarity_score"] > best_scores[pid]:
                best_scores[pid] = r["similarity_score"]

        # 유사도 점수 반영 + 내림차순 정렬
        for patent in patents:
            pid = patent["공개등록공보"]["patent_id"]
            patent["similarity_score"] = best_scores.get(pid, 0.0)

        patents.sort(key=lambda p: p["similarity_score"], reverse=True)

        # rank 재부여
        for i, patent in enumerate(patents):
            patent["rank"] = i + 1

    except Exception as e:
        logger.error("FAISS 유사도 계산 실패, 기본 순서 유지: %s", e)

    return patents


@app.post("/similarity", response_model=schemas.SimilarityResponse)
@limiter.limit(config.RATE_LIMIT_SIMILARITY)
def similarity_search(request: Request, response: Response, payload: schemas.SimilarityRequest):
    """
    사용자 쿼리 → KIPRIS 실제 데이터 → 청킹 → OpenAI 임베딩 → 코사인 유사도 FAISS → TOP K 반환
    """
    query = payload.query
    top_k = payload.top_k

    # 1. KIPRIS에서 실제 특허 데이터 가져오기
    if os.getenv("USE_MOCK", "false").lower() == "true":
        kipris_results = list(MOCK_SEARCH_RESPONSE["results"])
    else:
        kipris_results = fetch_patent_data_from_kipris(query)
        if not kipris_results:
            kipris_results = list(MOCK_SEARCH_RESPONSE["results"])

    # 2. FAISS 인덱스 (캐시 재사용)
    if query in _faiss_cache:
        index, chunks = _faiss_cache[query]
    else:
        chunks = chunk_patents(kipris_results)
        if chunks:
            index, chunks = build_faiss_index(chunks)
            _cache_put(_faiss_cache, query, (index, chunks))
        else:
            return {"query": query, "total_chunks": 0, "results": []}

    # 3. 유사도 검색
    results = search_similar(query, index, chunks, top_k=top_k)

    return {
        "query": query,
        "total_chunks": len(chunks),
        "results": results
    }

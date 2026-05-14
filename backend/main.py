import logging
import os
import re
import time

from fastapi import FastAPI, Depends, HTTPException
from starlette.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

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

# CORS 설정 — CORS_ORIGINS env로 제어 (기본 "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"[Profiling] {request.method} {request.url.path} completed in {process_time:.4f}s")
    return response

# ──────────────── 다국어 검색 지원 (영어 → 한국어 자동 번역) ────────────────

def is_korean(text: str) -> bool:
    """텍스트에 한글이 포함되어 있으면 True"""
    return bool(re.search(r"[가-힣]", text))


def translate_to_korean(text: str) -> str:
    """비한국어 입력을 KIPRIS 검색에 적합한 한국어 키워드로 번역.
    한국어 입력은 그대로 반환. 번역 실패 시 원문 fallback."""
    if is_korean(text):
        return text

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 특허 검색용 번역가입니다. 입력된 텍스트를 한국 특허청(KIPRIS) 검색에 적합한 한국어 키워드로 번역하세요. 번역 결과만 출력하고 설명은 하지 마세요."
                },
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=100,
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"번역: '{text}' → '{translated}'")
        return translated
    except Exception as e:
        logger.error(f"번역 실패, 원문 사용: {e}")
        return text
# ----------------- 팀원 작성 부분 (기본 작동 확인용) -----------------
@app.get("/")
def root():
    return {"message": "특허 분석 서버 작동 중!"}
# ---------------------------------------------------------------------
@app.post("/search", response_model=schemas.SearchResponse)
def search_patents(request: schemas.SearchRequest, db: Session = Depends(get_db)):
    """
    주어진 쿼리에 대해 KIPRIS API를 검색하고 결과를 반환합니다.
    영어 등 비한국어 입력 시 자동으로 한국어로 번역해서 검색합니다.
    """
    query = translate_to_korean(request.query)

    # 2) DB 캐시 조회 (필터/max_results는 캐시 후처리로 적용됨)
    cached = crud.get_cached_search(db, query, request)
    if cached is not None:
        logger.info("DB cache hit: %s", query)
        return {"query": query, "cached": True, "results": cached}

    # 3) 캐시 miss → KIPRIS 호출
    logger.info("DB cache miss. Fetching from KIPRIS: %s", query)
    t0 = time.time()
    fetch_count = max(request.max_results * 4, 30)
    parsed_results = fetch_patent_data_from_kipris(query, docs_count=fetch_count)
    t1 = time.time()
    logger.info(f"[Profiling] KIPRIS API Fetch took {t1 - t0:.4f}s")
    
    if not parsed_results:
        logger.warning("KIPRIS 결과 없음 → 빈 결과 반환")
        return {"query": query, "cached": False, "results": []}

    # FAISS 유사도 점수 적용 및 정렬 (DB에는 필터 이전 원본을 저장)
    t2 = time.time()
    parsed_results = _apply_faiss_scores(parsed_results, query)
    t3 = time.time()
    logger.info(f"[Profiling] FAISS Similarity Scoring took {t3 - t2:.4f}s")

    # DB 영구 저장 — 저장 실패는 응답을 막지 않음 (사용자 요청은 계속 처리)
    t4 = time.time()
    try:
        crud.save_search_results(db, query, parsed_results)
    except Exception as e:
        logger.error("DB 저장 실패 (응답은 계속): %s", e)
    t5 = time.time()
    logger.info(f"[Profiling] SQLite DB Cache Save took {t5 - t4:.4f}s")

    # 응답 직전 필터/제한/rank 재부여
    parsed_results = _apply_filters(parsed_results, request)
    parsed_results = parsed_results[:request.max_results]
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

    raise HTTPException(status_code=404, detail="Patent not found")

@app.post("/analyze", response_model=schemas.AnalyzeResponse)
def analyze_patent(request: schemas.AnalyzeRequest):
    """
    사용자 아이디어와 유사 특허 리스트를 받아 GPT-4o로 신규성 분석을 수행합니다.
    """
    patents_as_dict = [p.model_dump() for p in request.patents]
    result = llm.analyze_novelty(request.user_idea, patents_as_dict)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.get("/trend")
def get_trend(query: str):
    """
    키워드별 연도별 출원 트렌드.
    KIPRIS에서 최대 500건을 페이지네이션하여 출원연도별 실제 건수를 집계합니다.
    동일 쿼리는 메모리 캐시를 재사용합니다.
    """
    query = translate_to_korean(query)
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

        # 특허 ID별 최고 유사도 점수 집계 (ID 정규화 포함)
        best_scores: dict[str, float] = {}
        for r in chunk_results:
            pid = str(r["patent_id"]).strip()
            if pid not in best_scores or r["similarity_score"] > best_scores[pid]:
                best_scores[pid] = r["similarity_score"]

        # 유사도 점수 반영 + 내림차순 정렬
        for patent in patents:
            pid = str(patent["공개등록공보"]["patent_id"]).strip()
            if pid in best_scores:
                patent["similarity_score"] = float(best_scores[pid])
            else:
                patent["similarity_score"] = patent.get("similarity_score", 0.5)

        patents.sort(key=lambda p: p.get("similarity_score", 0.0), reverse=True)

        # rank 재부여
        for i, patent in enumerate(patents):
            patent["rank"] = i + 1

    except Exception as e:
        logger.error("FAISS 유사도 계산 실패, 기본 순서 유지: %s", e)

    return patents

# --- 수정
@app.post("/similarity", response_model=schemas.SimilarityResponse)
def similarity_search(request: schemas.SimilarityRequest):
    """..."""
    query = translate_to_korean(request.query)
    top_k = request.top_k

    # 1. KIPRIS에서 실제 특허 데이터 가져오기
    kipris_results = fetch_patent_data_from_kipris(query)
    if not kipris_results:
        return {"query": query, "total_chunks": 0, "results": []}

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

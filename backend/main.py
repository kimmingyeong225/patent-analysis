from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
import models, schemas
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
# 환경 변수 로드 (.env 파일)
load_dotenv()
# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)
app = FastAPI(title="특허 분석 시스템 API", version="1.0.0")

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 특정 도메인으로 제한하는 것이 좋음
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
def search_patents(request: schemas.SearchRequest, db: Session = Depends(get_db)):
    """
    주어진 쿼리에 대해 KIPRIS API를 검색하고 결과를 반환합니다.
    필터(출원연도 범위, 법적상태, 결과 수)를 적용하여 후처리합니다.
    """
    query = request.query
    # 필터가 있으면 넉넉하게 가져와서 후처리
    fetch_count = max(request.max_results * 4, 30)

    if os.getenv("USE_MOCK", "false").lower() == "true":
        print("USE_MOCK=true -> mock 데이터 사용")
        parsed_results = list(MOCK_SEARCH_RESPONSE["results"])
    else:
        parsed_results = fetch_patent_data_from_kipris(query, docs_count=fetch_count)
        if not parsed_results:
            print("Fallback to MOCK_DATA")
            parsed_results = list(MOCK_SEARCH_RESPONSE["results"])

    # ── 후처리 필터링 ──
    parsed_results = _apply_filters(parsed_results, request)

    # FAISS 코사인 유사도 점수 적용 및 정렬
    parsed_results = _apply_faiss_scores(parsed_results, query)

    # 최대 결과 수 제한
    parsed_results = parsed_results[:request.max_results]
    # rank 재부여
    for i, p in enumerate(parsed_results):
        p["rank"] = i + 1

    return {
        "query": query,
        "cached": False,
        "results": parsed_results
    }


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
    단일 특허 상세 조회
    초반 뼈대용으로 반환 폼만 구성
    """
    for result in MOCK_SEARCH_RESPONSE["results"]:
        if result["공개등록공보"]["patent_id"] == patent_id:
            return {
                "patent_id": patent_id,
                "공개등록공보": result["공개등록공보"]
            }

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
    if query in _trend_cache:
        print(f"Trend cache hit: {query}")
        cached = _trend_cache[query]
        return {"query": query, "trend_data": cached["trend_data"], "is_truncated": cached["is_truncated"]}

    print(f"Trend cache miss. Fetching from KIPRIS: {query}")
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
        print(f"FAISS 유사도 계산 실패, 기본 순서 유지: {e}")

    return patents


@app.post("/similarity", response_model=schemas.SimilarityResponse)
def similarity_search(request: schemas.SimilarityRequest):
    """
    사용자 쿼리 → KIPRIS 실제 데이터 → 청킹 → OpenAI 임베딩 → 코사인 유사도 FAISS → TOP K 반환
    """
    query = request.query
    top_k = request.top_k

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

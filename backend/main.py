from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
import models, schemas
from database import engine, get_db, Base
from kipris import fetch_patent_data_from_kipris
import llm
import crud

from fastapi.middleware.cors import CORSMiddleware

# FAISS 인덱스 메모리 캐시 — 동일 쿼리 재요청 시 임베딩 API 재호출 방지
_faiss_cache: dict = {}  # { query: (index, chunks) }
# 환경 변수 로드 (.env 파일)
load_dotenv()
# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)
app = FastAPI(title="특허 분석 시스템 API", version="1.0.0")

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 특정 도메인으로 제한하는 것이 좋음
    allow_credentials=True,
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
    DB 캐시를 먼저 확인하여 토큰 소모를 줄입니다.
    """
    query = request.query

    # 1. DB 캐시 확인
    cached_results = crud.get_search_results_by_query(db, query)
    if cached_results:
        print(f"Cache Hit for query: {query}")
        return {
            "query": query,
            "cached": True,
            "results": cached_results
        }

    # 2. 캐시 없으면 API 호출
    print(f"Cache Miss. Calling KIPRIS API for query: {query}")
    parsed_results = fetch_patent_data_from_kipris(query)
    if not parsed_results:
        print(f"KIPRIS API returned no results for query: {query}")
        parsed_results = []

    # FAISS 코사인 유사도 점수 적용 및 정렬
    parsed_results = _apply_faiss_scores(parsed_results, query)

    # 3. 결과 DB 저장
    for result in parsed_results:
        crud.save_patent(db, result)
        crud.create_search_result(
            db, 
            query=query, 
            patent_id=result["공개등록공보"]["patent_id"], 
            rank=result["rank"], 
            similarity_score=result["similarity_score"]
        )
    db.commit()

    return {
        "query": query,
        "cached": False,
        "results": parsed_results
    }
@app.get("/patent/{patent_id}")
def get_patent_detail(patent_id: str, db: Session = Depends(get_db)):
    """
    단일 특허 상세 조회. 먼저 DB를 확인하고 없으면 Mock(또는 상세 API)을 처리합니다.
    """
    # 1. DB 조회
    db_patent = crud.get_patent_by_id(db, patent_id)
    if db_patent:
        # DB 모델을 SearchResultItem의 '공개등록공보'와 '법적상태' 등으로 매핑하여 반환하거나 간단히 반환
        return {
            "patent_id": patent_id,
            "공개등록공보": {
                "patent_id": db_patent.patent_id,
                "title": db_patent.title,
                "abstract": db_patent.abstract,
                "applicant": db_patent.applicant,
                # ... 필요한 만큼 매핑
            }
        }

    raise HTTPException(status_code=404, detail="Patent not found")
@app.post("/analyze", response_model=schemas.AnalyzeResponse)
def analyze_patent(request: schemas.AnalyzeRequest):
    """
    사용자 아이디어와 유사 특허 리스트를 받아 GPT-4o로 신규성 분석을 수행합니다.
    """
    if not request.patents:
        raise HTTPException(status_code=400, detail="분석할 선행 특허가 없습니다.")

    patents_as_dict = [p.model_dump() for p in request.patents]
    result = llm.analyze_novelty(request.user_idea, patents_as_dict)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.get("/trend")
def get_trend(query: str):
    """
    키워드별 연도별 출원 트렌드 (초기 뼈대)
    """
    return {
        "query": query,
        "trend_data": [
            {"year": "2020", "count": 10},
            {"year": "2021", "count": 15},
            {"year": "2022", "count": 25},
        ]
    }

# ──────────────── 유사도 검색 엔드포인트 (팀원 2 추가) ────────────────

from embedding import chunk_patents, build_faiss_index, search_similar


def _apply_faiss_scores(patents: list, query: str) -> list:
    """
    KIPRIS 결과에 FAISS 코사인 유사도 점수를 적용합니다.
    특허별로 청크 중 최고 유사도를 대표 점수로 사용하고 내림차순 정렬합니다.
    동일 쿼리는 캐시된 인덱스를 재사용합니다.
    """
    try:
        chunks = chunk_patents(patents)
        if not chunks:
            return patents

        if query in _faiss_cache:
            index, chunks = _faiss_cache[query]
        else:
            index, chunks = build_faiss_index(chunks)
            _faiss_cache[query] = (index, chunks)

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
            # FAISS 점수가 있으면 반영, 없으면 기존 점수(KIPRIS 기본값) 유지 혹은 0.5 기본값
            if pid in best_scores:
                patent["similarity_score"] = float(best_scores[pid])
            else:
                # 점수 누락 방지를 위한 기본 유사도 부여 (0.0 방지)
                patent["similarity_score"] = patent.get("similarity_score", 0.5)

        patents.sort(key=lambda p: p.get("similarity_score", 0.0), reverse=True)

        # rank 재부여
        for i, patent in enumerate(patents):
            patent["rank"] = i + 1

    except Exception as e:
        print(f"FAISS 유사도 계산 실패, 기본 순서 유지: {e}")

    return patents


@app.post("/similarity", response_model=schemas.SimilarityResponse)
def similarity_search(request: schemas.SimilarityRequest, db: Session = Depends(get_db)):
    """
    사용자 쿼리 → KIPRIS 실제 데이터 → 청킹 → OpenAI 임베딩 → 코사인 유사도 FAISS → TOP K 반환
    """
    query = request.query
    top_k = request.top_k

    # 1. KIPRIS 또는 DB에서 실제 특허 데이터 가져오기
    # 1. KIPRIS 또는 DB에서 실제 특허 데이터 가져오기
    # DB 캐시 먼저 확인
    cached_results = crud.get_search_results_by_query(db, query)
    if cached_results:
        print(f"Similarity Search: Cache Hit for query: {query}")
        kipris_results = cached_results
    else:
        print(f"Similarity Search: Cache Miss. Calling KIPRIS API for query: {query}")
        kipris_results = fetch_patent_data_from_kipris(query)
        if not kipris_results:
            print(f"Similarity Search: KIPRIS API returned no results for query: {query}")
            kipris_results = []
        
        # 결과 DB 저장
        for result in kipris_results:
            crud.save_patent(db, result)
        db.commit()

    # 2. 특허 데이터 청킹
    chunks = chunk_patents(kipris_results)

    # 3. FAISS 인덱스 생성 (임베딩 포함)
    index, chunks = build_faiss_index(chunks)

    # 4. 유사도 검색
    results = search_similar(query, index, chunks, top_k=top_k)

    return {
        "query": query,
        "total_chunks": len(chunks),
        "results": results
    }
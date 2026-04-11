from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv  
import os                       
import models, schemas
from database import engine, get_db, Base
from kipris import fetch_patent_data_from_kipris
from mock_data import MOCK_SEARCH_RESPONSE
import llm
# 환경 변수 로드 (.env 파일)
load_dotenv()
# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)
app = FastAPI(title="특허 분석 시스템 API", version="1.0.0")
# ----------------- 팀원 작성 부분 (기본 작동 확인용) -----------------
@app.get("/")
def root():
    return {"message": "특허 분석 서버 작동 중!"}
# ---------------------------------------------------------------------
@app.post("/search", response_model=schemas.SearchResponse)
def search_patents(request: schemas.SearchRequest, db: Session = Depends(get_db)):
    """
    주어진 쿼리에 대해 KIPRIS API를 검색하고 결과를 반환합니다.
    초기 뼈대: KIPRIS 검색 후 결과를 바로 반환 (캐싱/DB 저장 로직은 확장 가능)
    """
    query = request.query
    
    # KIPRIS API 연동 시도
    parsed_results = fetch_patent_data_from_kipris(query)
    
    if not parsed_results:
        print("Fallback to MOCK_DATA")
        parsed_results = list(MOCK_SEARCH_RESPONSE["results"])

    # FAISS 코사인 유사도 점수 적용 및 정렬
    parsed_results = _apply_faiss_scores(parsed_results, query)

    return {
        "query": query,
        "cached": False,
        "results": parsed_results
    }
@app.get("/patent/{patent_id}")
def get_patent_detail(patent_id: str, db: Session = Depends(get_db)):
    """
    단일 특허 상세 조회
    초반 뼈대용으로 반환 폼만 구성
    """
    # 우선 mock data에서 아이디 비교 후 반환하도록 테스트 처리 (또는 DB 조회)
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
    """
    try:
        chunks = chunk_patents(patents)
        if not chunks:
            return patents

        index, chunks = build_faiss_index(chunks)
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
    kipris_results = fetch_patent_data_from_kipris(query)

    # KIPRIS 실패 시 Mock 데이터 사용
    if not kipris_results:
        kipris_results = MOCK_SEARCH_RESPONSE["results"]

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
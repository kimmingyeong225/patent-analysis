from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv  
import os                       
import models, schemas
from database import engine, get_db, Base
from kipris import fetch_patent_data_from_kipris
from mock_data import MOCK_SEARCH_RESPONSE
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
        # KIPRIS API 호출이 실패하거나 결과가 없으면 Mock 데이터를 반환합니다.
        print("Fallback to MOCK_DATA")
        return MOCK_SEARCH_RESPONSE
        
    response_data = {
        "query": query,
        "cached": False,
        "results": parsed_results
    }
    
    # 향후 여기에 DB 캐싱 로직 추가 (models.Patent 등에 저장)
    
    return response_data
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

#  유사도 검색 엔드포인트  

from embedding import chunk_patents, build_faiss_index, search_similar

@app.post("/similarity", response_model=schemas.SimilarityResponse)
def similarity_search(request: schemas.SimilarityRequest):
    """
    사용자 쿼리 → Mock 특허 청킹 → OpenAI 임베딩 → 코사인 유사도 FAISS → TOP K 반환
    """
    query = request.query
    top_k = request.top_k

    # 1. 특허 데이터 청킹
    chunks = chunk_patents(MOCK_SEARCH_RESPONSE["results"])

    # 2. FAISS 인덱스 생성 (임베딩 포함)
    index, chunks = build_faiss_index(chunks)

    # 3. 유사도 검색
    results = search_similar(query, index, chunks, top_k=top_k)

    return {
        "query": query,
        "total_chunks": len(chunks),
        "results": results
    }
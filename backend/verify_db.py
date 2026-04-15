from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import crud
import models

# 테이블 생성 (혹시 모르니)
Base.metadata.create_all(bind=engine)

def verify():
    db = SessionLocal()
    query = "test_query_123"
    
    # 1. 초기 상태 확인 (데이터 없어야 함)
    results = crud.get_search_results_by_query(db, query)
    print(f"Initial check for '{query}': {'Found' if results else 'Not Found'}")
    
    # 2. 가상 데이터 저장
    mock_item = {
        "rank": 1,
        "similarity_score": 0.99,
        "공개등록공보": {
            "patent_id": "KR1012345678",
            "application_number": "10-2024-0012345",
            "title": "테스트 특허",
            "applicant": "테스트 주식회사",
            "inventor": "홍길동",
            "application_date": "2024-01-01",
            "publication_date": "2024-06-01",
            "registration_date": None,
            "abstract": "본 발명은 테스트를 위한 것입니다.",
            "claims": ["청구항 1"],
            "doc_type": "공개"
        },
        "인용문헌": {
            "cited_by_count": 0,
            "citing_count": 0,
            "cited_patents": []
        },
        "법적상태": {
            "status": "공개",
            "status_code": "A",
            "last_event": "공개",
            "last_event_date": "2024-06-01",
            "is_alive": True
        },
        "분류코드": {
            "ipc": [{"code": "G06F", "desc": "컴퓨터"}],
            "cpc": []
        }
    }
    
    print("Saving mock data to DB...")
    crud.save_patent(db, mock_item)
    crud.create_search_result(db, query, "KR1012345678", 1, 0.99)
    db.commit()
    
    # 3. 다시 조회 (데이터 있어야 함)
    results = crud.get_search_results_by_query(db, query)
    if results:
        print(f"After save check for '{query}': Found {len(results)} items")
        print(f"First item title: {results[0]['공개등록공보']['title']}")
    else:
        print(f"After save check for '{query}': Still Not Found!")
        
    db.close()

if __name__ == "__main__":
    verify()

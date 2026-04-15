from sqlalchemy.orm import Session
import models
import schemas

def get_patent_by_id(db: Session, patent_id: str):
    return db.query(models.Patent).filter(models.Patent.patent_id == patent_id).first()

def get_search_results_by_query(db: Session, query: str):
    """
    쿼리로 검색된 결과를 가져옵니다. 
    검색 결과 데이터뿐만 아니라 연결된 Patent 정보들도 함께 가져와서 
    SearchResponse 스키마에 맞게 변환하기 쉬운 형태로 반환합니다.
    """
    # query를 기준으로 search_results 테이블 조회
    results = db.query(models.SearchResult).filter(models.SearchResult.query == query).order_by(models.SearchResult.rank).all()
    
    if not results:
        return None
        
    mapped_results = []
    for res in results:
        patent = res.patent
        if not patent:
            continue
            
        # Citation, LegalStatus, Classification 정보 로드
        citation = patent.citation
        legal_status = patent.legal_status
        classifications = patent.classifications
        
        ipc_list = [{"code": c.code, "desc": c.desc} for c in classifications if c.code_type == "ipc"]
        cpc_list = [{"code": c.code, "desc": c.desc} for c in classifications if c.code_type == "cpc"]

        mapped_item = {
            "rank": res.rank,
            "similarity_score": res.similarity_score,
            "공개등록공보": {
                "patent_id": patent.patent_id,
                "application_number": patent.application_number,
                "title": patent.title,
                "applicant": patent.applicant,
                "inventor": patent.inventor,
                "application_date": patent.application_date,
                "publication_date": patent.publication_date,
                "registration_date": patent.registration_date,
                "abstract": patent.abstract,
                "claims": patent.claims or [],
                "doc_type": patent.doc_type
            },
            "인용문헌": {
                "cited_by_count": citation.cited_by_count if citation else 0,
                "citing_count": citation.citing_count if citation else 0,
                "cited_patents": citation.cited_patents if citation else []
            },
            "법적상태": {
                "status": legal_status.status if legal_status else "알 수 없음",
                "status_code": legal_status.status_code if legal_status else "UNKNOWN",
                "last_event": legal_status.last_event if legal_status else "",
                "last_event_date": legal_status.last_event_date if legal_status else "",
                "is_alive": legal_status.is_alive if legal_status else False
            },
            "분류코드": {
                "ipc": ipc_list,
                "cpc": cpc_list
            }
        }
        mapped_results.append(mapped_item)
        
    return mapped_results

def save_patent(db: Session, patent_data: dict):
    """
    patent_data(SearchResultItem 형태의 dict)를 DB에 저장합니다.
    이미 존재하면 업데이트하거나 건너뜁니다.
    """
    pub_info = patent_data["공개등록공보"]
    patent_id = pub_info["patent_id"]
    
    # 1. Patent 저장
    db_patent = get_patent_by_id(db, patent_id)
    if not db_patent:
        db_patent = models.Patent(
            patent_id=patent_id,
            application_number=pub_info.get("application_number"),
            title=pub_info.get("title"),
            applicant=pub_info.get("applicant"),
            inventor=pub_info.get("inventor"),
            application_date=pub_info.get("application_date"),
            publication_date=pub_info.get("publication_date"),
            registration_date=pub_info.get("registration_date"),
            abstract=pub_info.get("abstract"),
            claims=pub_info.get("claims"),
            doc_type=pub_info.get("doc_type")
        )
        db.add(db_patent)
        db.flush() # ID를 얻기 위해 flush
    
    # 2. LegalStatus 저장
    ls_data = patent_data["법적상태"]
    if not db_patent.legal_status:
        db_ls = models.LegalStatus(
            patent_id=patent_id,
            status=ls_data.get("status"),
            status_code=ls_data.get("status_code"),
            last_event=ls_data.get("last_event"),
            last_event_date=ls_data.get("last_event_date"),
            is_alive=ls_data.get("is_alive")
        )
        db.add(db_ls)
        
    # 3. Citation 저장
    cite_data = patent_data["인용문헌"]
    if not db_patent.citation:
        db_cite = models.Citation(
            patent_id=patent_id,
            cited_by_count=cite_data.get("cited_by_count", 0),
            citing_count=cite_data.get("citing_count", 0),
            cited_patents=cite_data.get("cited_patents", [])
        )
        db.add(db_cite)
        
    # 4. Classification 저장
    cls_data = patent_data["분류코드"]
    if not db_patent.classifications:
        for ipc in cls_data.get("ipc", []):
            db.add(models.Classification(
                patent_id=patent_id,
                code_type="ipc",
                code=ipc.get("code"),
                desc=ipc.get("desc", "")
            ))
        for cpc in cls_data.get("cpc", []):
            db.add(models.Classification(
                patent_id=patent_id,
                code_type="cpc",
                code=cpc.get("code"),
                desc=cpc.get("desc", "")
            ))
            
    return db_patent

def create_search_result(db: Session, query: str, patent_id: str, rank: int, similarity_score: float):
    """
    특정 쿼리에 대한 검색 결과 매핑을 저장합니다.
    """
    db_result = models.SearchResult(
        query=query,
        patent_id=patent_id,
        rank=rank,
        similarity_score=similarity_score
    )
    db.add(db_result)
    return db_result

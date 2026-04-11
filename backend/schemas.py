from pydantic import BaseModel
from typing import List, Optional

class SearchRequest(BaseModel):
    query: str

class ClassificationItem(BaseModel):
    code: str
    desc: str

class ClassificationCodes(BaseModel):
    ipc: List[ClassificationItem] = []
    cpc: List[ClassificationItem] = []

class LegalStatusModel(BaseModel):
    status: str
    status_code: str
    last_event: str
    last_event_date: str
    is_alive: bool

class CitationModel(BaseModel):
    cited_by_count: int
    citing_count: int
    cited_patents: List[str]

class PatentInfo(BaseModel):
    patent_id: str
    application_number: str
    title: str
    applicant: str
    inventor: str
    application_date: str
    publication_date: str
    registration_date: Optional[str] = None
    abstract: str
    claims: List[str]
    doc_type: str

class SearchResultItem(BaseModel):
    rank: int
    similarity_score: float
    공개등록공보: PatentInfo
    인용문헌: CitationModel
    법적상태: LegalStatusModel
    분류코드: ClassificationCodes

class SearchResponse(BaseModel):
    query: str
    cached: bool
    results: List[SearchResultItem]

# 유사도 검색 스키마

class SimilarityRequest(BaseModel):
    query: str
    top_k: int = 5

class SimilarChunkItem(BaseModel):
    rank: int
    patent_id: str
    section: str
    text: str
    similarity_score: float

class SimilarityResponse(BaseModel):
    query: str
    total_chunks: int
    results: list[SimilarChunkItem]

    
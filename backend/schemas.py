from pydantic import BaseModel
from typing import Any, Dict, List, Optional

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


# ── /analyze 스키마 ──────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    user_idea: str
    patents: List[SearchResultItem]


class PriorArtItem(BaseModel):
    patent_id: str
    title: str
    overlap: str
    difference: str
    threat_level: str


class FiveAspects(BaseModel):
    innovation_point: str
    implementation: str
    marketability: str
    design_around: str
    registrability: str


class AnalyzeResponse(BaseModel):
    patent_title: str
    summary: str
    prior_art_comparison: List[PriorArtItem]
    five_aspects: FiveAspects
    novelty_score: int
    novelty_reason: str
    risk_level: str
    risk_reason: str
    recommendation: str


# ── /similarity 스키마 ───────────────────────────────────────
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
    results: List[SimilarChunkItem]

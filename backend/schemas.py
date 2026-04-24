from pydantic import BaseModel
from typing import Any, Dict, List, Literal, Optional

class SearchRequest(BaseModel):
    query: str
    year_from: Optional[int] = None       # 출원연도 시작 (예: 2020)
    year_to: Optional[int] = None         # 출원연도 끝 (예: 2025)
    status: Optional[str] = None          # 법적상태 필터 ("등록" | "공개" | "소멸" 등, None이면 전체)
    max_results: int = 5                  # 반환 결과 수 (5 / 10 / 15)

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
    last_event_date: Optional[str] = None
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
    publication_date: Optional[str] = None
    registration_date: Optional[str] = None
    abstract: str = "요약이 제공되지 않았습니다."
    claims: List[str] = []
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
    # source — 결과 출처 투명화 (Phase 1-F). 기본값 "kipris"로 하위 호환.
    #   "kipris" : 실시간 KIPRIS 호출 (빈 결과 포함)
    #   "mock"   : USE_MOCK=true 환경변수 분기
    #   "cache"  : DB 영구 캐시 hit
    source: Literal["kipris", "mock", "cache"] = "kipris"
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
    risk_level: Literal["높음", "중간", "낮음"]
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

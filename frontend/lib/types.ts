export interface Publication {
  patent_id: string;
  title: string;
  applicant: string;
  inventor: string;
  application_number: string;
  application_date: string;
  publication_date?: string | null;
  registration_date?: string | null;
  doc_type: string;
  abstract: string;
  claims?: string[];
}

export interface LegalStatus {
  status: string;
  status_code: string;
  last_event: string;
  last_event_date?: string | null;
  is_alive: boolean;
}

export interface Citation {
  cited_by_count: number;
  citing_count: number;
  cited_patents: string[];
}

export interface ClassificationItem {
  code: string;
  desc: string;
}

export interface ClassificationCodes {
  ipc: ClassificationItem[];
  cpc: ClassificationItem[];
}

export interface PatentResult {
  rank: number;
  similarity_score: number;
  공개등록공보: Publication;
  법적상태: LegalStatus;
  인용문헌: Citation;
  분류코드: ClassificationCodes;
}

export interface FiveAspects {
  innovation_point: string;
  implementation: string;
  marketability: string;
  design_around: string;
  registrability: string;
}

export interface PriorArtComparison {
  patent_id: string;
  title: string;
  threat_level: string;
  overlap: string;
  difference: string;
}

export interface Analysis {
  novelty_score: number;
  novelty_reason: string;
  risk_level: "높음" | "중간" | "낮음";
  patent_title: string;
  summary: string;
  risk_reason: string;
  recommendation: string;
  five_aspects: FiveAspects;
  prior_art_comparison: PriorArtComparison[];
}

export interface SearchResponse {
  results: PatentResult[];
  cached: boolean;
  // Phase 1-F: 결과 출처 투명화. 백엔드가 기본값 "kipris"로 항상 반환.
  source: "kipris" | "mock" | "cache";
}

// Phase 1-F.1: /similarity 응답. DB 영구 캐시 없음 → "cache" 값 없음.
// 현재 프론트에서 호출하는 컴포넌트는 없지만 타입만 선제 동기화.
export interface SimilarChunkItem {
  rank: number;
  patent_id: string;
  section: string;
  text: string;
  similarity_score: number;
}

export interface SimilarityResponse {
  query: string;
  total_chunks: number;
  source: "kipris" | "mock";
  results: SimilarChunkItem[];
}

export interface SearchFilters {
  year_from?: number | null;
  year_to?: number | null;
  status?: string | null;
  max_results?: number;
}

export type ViewState = "home" | "loading" | "results";

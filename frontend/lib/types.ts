export interface Publication {
  patent_id: string;
  title: string;
  applicant: string;
  inventor: string;
  application_number: string;
  application_date: string;
  publication_date: string;
  registration_date?: string | null;
  doc_type: string;
  abstract: string;
  claims?: string[];
}

export interface LegalStatus {
  status: string;
  status_code: string;
  last_event: string;
  last_event_date: string;
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
}

export type ViewState = "home" | "loading" | "results";

export interface Publication {
  title: string;
  applicant: string;
  application_number: string;
  application_date: string;
  publication_date: string;
  doc_type: string;
  abstract: string;
  claims?: string[];
}

export interface LegalStatus {
  status: string;
  is_alive: boolean;
}

export interface PatentResult {
  rank: number;
  similarity_score: string;
  공개등록공보: Publication;
  법적상태: LegalStatus;
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

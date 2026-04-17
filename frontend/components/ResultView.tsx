"use client";

import StickyHeader from "./StickyHeader";
import AISummaryWidget from "./AISummaryWidget";
import PriorArtComparison from "./PriorArtComparison";
import PatentList from "./PatentList";
import TrendChart from "./TrendChart";
import type { PatentResult, Analysis } from "@/lib/types";

function buildReport(query: string, patents: PatentResult[], analysis: Analysis): string {
  const lines = [
    "# PatentAI 신규성 분석 리포트",
    "",
    `**분석 아이디어:** ${query}`,
    "",
    "---",
    "",
    `## 신규성 점수: ${analysis.novelty_score} / 100`,
    `**리스크 수준:** ${analysis.risk_level}`,
    `**제안 특허명:** ${analysis.patent_title}`,
    "",
    "## 분석 요약",
    analysis.summary,
    "",
    "## 리스크 근거",
    analysis.risk_reason,
    "",
    "## 출원 전략 조언",
    analysis.recommendation,
    "",
    "---",
    "",
    "## 유사 특허 목록",
    ...patents.map((p) => {
      const pct = Math.round(p.similarity_score * 100);
      return `- **${p.rank}위** | ${p.공개등록공보.title} | 유사도 ${pct}% | ${p.공개등록공보.application_number}`;
    }),
  ];
  return lines.join("\n");
}

/* ── 분석 스켈레톤 ────────────────────────────── */
function AnalysisSkeleton() {
  return (
    <section className="bg-blue-50 border border-blue-100 rounded-2xl p-6 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        <span className="text-sm font-semibold text-blue-500">
          AI 신규성 분석 중…
        </span>
      </div>
      <div className="space-y-3">
        <div className="h-4 bg-blue-100 rounded w-3/4" />
        <div className="h-4 bg-blue-100 rounded w-1/2" />
        <div className="h-4 bg-blue-100 rounded w-5/6" />
        <div className="h-4 bg-blue-100 rounded w-2/3" />
      </div>
      <p className="text-xs text-blue-400 mt-4">
        GPT-4o가 선행특허를 비교 분석하고 있습니다. 보통 10~20초 소요됩니다.
      </p>
    </section>
  );
}

interface ResultViewProps {
  query: string;
  patents: PatentResult[];
  analysis: Analysis | null;
  analyzing?: boolean;
  onSearch: (q: string) => void;
  onHome: () => void;
  history?: string[];
  onRemoveHistory?: (q: string) => void;
}

export default function ResultView({
  query,
  patents,
  analysis,
  analyzing = false,
  onSearch,
  onHome,
  history = [],
  onRemoveHistory,
}: ResultViewProps) {
  const handleDownload = () => {
    if (!analysis) return;
    const md  = buildReport(query, patents, analysis);
    const blob = new Blob([md], { type: "text/markdown" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `patent_analysis_${query.slice(0, 20).replace(/[\s/\\:*?"<>|]/g, "_")}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 고정 헤더 */}
      <StickyHeader
        currentQuery={query}
        onSearch={onSearch}
        onLogoClick={onHome}
        history={history}
        onRemoveHistory={onRemoveHistory}
      />

      {/* 메인 콘텐츠 */}
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        {/* ① AI 신규성 분석 위젯 — 로딩 중이면 스켈레톤 */}
        {analysis ? (
          <AISummaryWidget analysis={analysis} onDownload={handleDownload} />
        ) : analyzing ? (
          <AnalysisSkeleton />
        ) : null}

        {/* ② 선행특허별 상세 비교 — 분석 완료 후에만 표시 */}
        {analysis && (
          <PriorArtComparison comparisons={analysis.prior_art_comparison} />
        )}

        {/* ③ 유사 특허 리스트 — 항상 먼저 표시 */}
        <PatentList patents={patents} />

        {/* ④ 연도별 트렌드 차트 */}
        <TrendChart initialKeyword={query} />
      </main>
    </div>
  );
}

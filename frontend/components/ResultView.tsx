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
      const pct = Math.round(parseFloat(p.similarity_score) * 100);
      return `- **${p.rank}위** | ${p.공개등록공보.title} | 유사도 ${pct}% | ${p.공개등록공보.application_number}`;
    }),
  ];
  return lines.join("\n");
}

interface ResultViewProps {
  query: string;
  patents: PatentResult[];
  analysis: Analysis | null;
  error: string | null;
  onSearch: (q: string) => void;
  onHome: () => void;
  history?: string[];
  onRemoveHistory?: (q: string) => void;
}

export default function ResultView({
  query,
  patents,
  analysis,
  error,
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
    a.download = `patent_analysis_${query.slice(0, 20).replace(/\s/g, "_")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const hasPatents = patents.length > 0;

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
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {!hasPatents && !error && (
           <div className="bg-white border border-slate-200 text-slate-600 px-6 py-12 rounded-xl text-center shadow-sm">
             <p className="text-lg font-medium">검색 결과가 없습니다.</p>
             <p className="text-sm mt-1 text-slate-400">다른 키워드로 검색해 보세요.</p>
           </div>
        )}

        {/* ① AI 신규성 분석 위젯 */}
        {analysis && (
          <>
            <AISummaryWidget analysis={analysis} onDownload={handleDownload} />
            <PriorArtComparison comparisons={analysis.prior_art_comparison} />
          </>
        )}

        {hasPatents && (
          <>
            <PatentList patents={patents} />
            <TrendChart initialKeyword={query} />
          </>
        )}
      </main>
    </div>
  );
}

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

interface ResultViewProps {
  query: string;
  patents: PatentResult[];
  analysis: Analysis;
  onSearch: (q: string) => void;
  onHome: () => void;
  history?: string[];
  onRemoveHistory?: (q: string) => void;
}

export default function ResultView({
  query,
  patents,
  analysis,
  onSearch,
  onHome,
  history = [],
  onRemoveHistory,
}: ResultViewProps) {
  const handleDownload = () => {
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
        {/* ① AI 신규성 분석 위젯 */}
        <AISummaryWidget analysis={analysis} onDownload={handleDownload} />

        {/* ② 선행특허별 상세 비교 */}
        <PriorArtComparison comparisons={analysis.prior_art_comparison} />

        {/* ③ 유사 특허 리스트 */}
        <PatentList patents={patents} />

        {/* ④ 연도별 트렌드 차트 */}
        <TrendChart initialKeyword={query} />
      </main>
    </div>
  );
}

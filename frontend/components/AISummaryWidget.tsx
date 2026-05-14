"use client";

import { useState } from "react";
import { Download, AlertTriangle, CheckCircle, Info } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { Analysis } from "@/lib/types";

/* ── 리스크 설정 ─────────────────────────────── */
const RISK_CONFIG = {
  높음: {
    label: "리스크 높음",
    badgeCls: "bg-red-100 text-red-700",
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    scoreColor: "text-red-600",
    barColor: "bg-red-500",
  },
  중간: {
    label: "리스크 중간",
    badgeCls: "bg-amber-100 text-amber-700",
    icon: <Info className="w-3.5 h-3.5" />,
    scoreColor: "text-amber-600",
    barColor: "bg-amber-500",
  },
  낮음: {
    label: "리스크 낮음",
    badgeCls: "bg-green-100 text-green-700",
    icon: <CheckCircle className="w-3.5 h-3.5" />,
    scoreColor: "text-green-600",
    barColor: "bg-green-500",
  },
};

/* ── 5가지 관점 탭 정의 ──────────────────────── */
const ASPECT_TABS = [
  { key: "innovation_point" as const, label: "🚀 혁신 포인트" },
  { key: "implementation"   as const, label: "🔧 구현 방법"   },
  { key: "marketability"    as const, label: "📈 시장성"       },
  { key: "design_around"   as const, label: "🛡️ 회피 설계"   },
  { key: "registrability"  as const, label: "✅ 등록 가능성"  },
] as const;

type AspectKey = typeof ASPECT_TABS[number]["key"];

/* ── 탭 콘텐츠를 bullet 리스트로 포맷 ────────── */
function formatAspect(text: string): string[] {
  if (!text || text === "분석 데이터 없음") return ["분석 데이터 없음"];
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  return lines.length > 1
    ? lines
    : text.split(". ").map((s) => s.trim()).filter(Boolean).map((s) => (s.endsWith(".") ? s : `${s}.`));
}

/* ── 분석 요약 불릿 포인트 ──────────────────────
   줄글 요약을 문장 단위로 분리해 • 리스트로 렌더링.
   내용은 100% 보존하고 표현 형식만 변경합니다.
──────────────────────────────────────────────── */
function SummaryBullets({ text }: { text: string }) {
  const sentences = text
    .split(/\n+/)
    .flatMap((line) => line.split(/(?<=[.!?])\s+/))
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length <= 1) {
    return <p className="text-sm text-slate-600 leading-relaxed">{text}</p>;
  }

  return (
    <ul className="space-y-2">
      {sentences.map((s, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-slate-600 leading-relaxed">
          <span className="text-blue-400 font-bold shrink-0 mt-0.5 select-none">•</span>
          <span>{s}</span>
        </li>
      ))}
    </ul>
  );
}

/* ── Props ───────────────────────────────────── */
interface AISummaryWidgetProps {
  analysis: Analysis;
  onDownload: () => void;
}

export default function AISummaryWidget({ analysis, onDownload }: AISummaryWidgetProps) {
  const [activeTab, setActiveTab] = useState<AspectKey>("innovation_point");

  const risk  = RISK_CONFIG[analysis.risk_level] ?? RISK_CONFIG["중간"];
  const score = analysis.novelty_score;

  return (
    <section className="bg-blue-50 border border-blue-100 rounded-2xl p-6 animate-slide-up">

      {/* ── 헤더: 레이블 + 다운로드 ── */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-blue-500 uppercase tracking-widest font-mono">
          AI 신규성 분석
        </span>
        <button
          onClick={onDownload}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-blue-600 transition-colors"
        >
          <Download className="w-3.5 h-3.5" />
          리포트 다운로드
        </button>
      </div>

      {/* ── 제안 특허명 ── */}
      <div className="bg-white/70 border border-blue-100 rounded-xl px-4 py-3 mb-5">
        <p className="text-xs font-semibold text-blue-400 uppercase tracking-wider font-mono mb-1">
          AI 제안 특허명
        </p>
        <p className="text-sm font-bold text-slate-800 leading-snug">
          {analysis.patent_title}
        </p>
      </div>

      {/* ── 점수 + 요약 ── */}
      <div className="flex gap-7 items-start mb-5">
        {/* 좌측: 점수 */}
        <div className="shrink-0 text-center w-24">
          <div className={`text-6xl font-bold leading-none ${risk.scoreColor}`}>
            {score}
          </div>
          <div className="text-slate-400 text-xs mt-1">/100</div>
          <div className="mt-3">
            <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
              <div
                className={`h-full ${risk.barColor} rounded-full`}
                style={{ width: `${score}%` }}
              />
            </div>
          </div>
          <div className={`mt-3 inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ${risk.badgeCls}`}>
            {risk.icon}
            {risk.label}
          </div>
        </div>

        {/* 우측: 분석 요약 + 전략 조언 */}
        <div className="flex-1 min-w-0 space-y-3.5">
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-1.5">분석 요약</p>
            <SummaryBullets text={analysis.summary} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-1.5">출원 전략 조언</p>
            <p className="text-sm text-slate-500 leading-relaxed">{analysis.recommendation}</p>
          </div>
        </div>
      </div>

      {/* ── 구분선 ── */}
      <div className="border-t border-blue-100 mb-4" />

      {/* ── 5가지 관점 탭 ── */}
      <div>
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono mb-3">
          5가지 관점 분석
        </p>

        {/* Pill 탭 메뉴 */}
        <div className="flex flex-wrap gap-2 mb-4">
          {ASPECT_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`text-xs font-medium px-3.5 py-1.5 rounded-full border transition-all whitespace-nowrap ${
                activeTab === tab.key
                  ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                  : "bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-600"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* 탭 콘텐츠 (Framer Motion 전환) */}
        <div className="bg-white/70 border border-blue-100 rounded-xl px-4 py-3 min-h-[80px]">
          <AnimatePresence mode="wait">
            <motion.ul
              key={activeTab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="space-y-1.5"
            >
              {formatAspect(analysis.five_aspects[activeTab]).map((line, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-600 leading-relaxed">
                  <span className="text-blue-300 shrink-0 mt-0.5 font-mono text-xs">—</span>
                  {line}
                </li>
              ))}
            </motion.ul>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}

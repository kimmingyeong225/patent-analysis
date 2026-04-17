"use client";

import { XCircle, CheckCircle2 } from "lucide-react";
import type { PriorArtComparison as PriorArtType } from "@/lib/types";

/* ── 위협도 설정 ─────────────────────────────── */
const THREAT_CONFIG = {
  높음: {
    dot: "🔴",
    badgeCls: "bg-red-50 text-red-600 border border-red-100",
    cardBorder: "border-red-100",
    headerBg: "bg-red-50/50",
  },
  중간: {
    dot: "🟡",
    badgeCls: "bg-amber-50 text-amber-600 border border-amber-100",
    cardBorder: "border-amber-100",
    headerBg: "bg-amber-50/50",
  },
  낮음: {
    dot: "🟢",
    badgeCls: "bg-green-50 text-green-600 border border-green-100",
    cardBorder: "border-green-100",
    headerBg: "bg-green-50/30",
  },
};

/* ── 단일 비교 카드 ───────────────────────────── */
function ComparisonCard({ item }: { item: PriorArtType }) {
  const cfg = THREAT_CONFIG[item.threat_level as keyof typeof THREAT_CONFIG] ?? THREAT_CONFIG["낮음"];

  return (
    <div className={`bg-white border ${cfg.cardBorder} rounded-xl overflow-hidden`}>
      {/* 헤더 */}
      <div className={`flex items-center gap-2.5 px-4 py-3 ${cfg.headerBg} border-b ${cfg.cardBorder}`}>
        <span
          className={`shrink-0 inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ${cfg.badgeCls}`}
        >
          {cfg.dot} {item.threat_level}
        </span>
        <span className="text-sm font-semibold text-slate-700 truncate flex-1">
          {item.title}
        </span>
        <span className="shrink-0 text-xs text-slate-400 font-mono">{item.patent_id}</span>
      </div>

      {/* 본문: 겹치는 부분 / 차별점 */}
      <div className="grid grid-cols-2 divide-x divide-gray-100">
        {/* 겹치는 부분 */}
        <div className="px-4 py-3">
          <div className="flex items-center gap-1.5 mb-2">
            <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
            <span className="text-xs font-semibold text-red-500 uppercase tracking-wider">
              겹치는 부분
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{item.overlap}</p>
        </div>

        {/* 차별점 */}
        <div className="px-4 py-3">
          <div className="flex items-center gap-1.5 mb-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500 shrink-0" />
            <span className="text-xs font-semibold text-green-600 uppercase tracking-wider">
              차별점
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{item.difference}</p>
        </div>
      </div>
    </div>
  );
}

/* ── 섹션 컨테이너 ──────────────────────────── */
interface PriorArtComparisonProps {
  comparisons: PriorArtType[];
}

export default function PriorArtComparison({ comparisons }: PriorArtComparisonProps) {
  if (!comparisons || comparisons.length === 0) return null;


  return (
    <section className="animate-slide-up">
      <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest font-mono mb-3">
        선행특허별 상세 비교
      </h2>
      <div className="space-y-2.5">
        {comparisons.map((item) => (
          <ComparisonCard key={item.patent_id} item={item} />
        ))}
      </div>
    </section>
  );
}

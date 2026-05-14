"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink, Info } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { PatentResult } from "@/lib/types";
import PatentDetailModal from "./PatentDetailModal";

/* ── 유사도 색상 ──────────────────────────────── */
function scoreStyle(pct: number) {
  if (pct >= 80) return { text: "text-red-600",    bg: "bg-red-50",    border: "border-red-100" };
  if (pct >= 60) return { text: "text-amber-600",  bg: "bg-amber-50",  border: "border-amber-100" };
  return           { text: "text-blue-600",    bg: "bg-blue-50",   border: "border-blue-100" };
}

/* ── 법적상태 배지 ────────────────────────────── */
function StatusBadge({ status, isAlive }: { status: string; isAlive: boolean }) {
  const cls = isAlive
    ? status === "등록"
      ? "bg-green-100 text-green-700"
      : "bg-sky-100 text-sky-700"
    : "bg-gray-100 text-gray-500";
  return (
    <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${cls}`}>
      {status}
    </span>
  );
}

/* ── 특허 한 행 ────────────────────────────────── */
function PatentRow({
  patent,
  onOpenDetail,
}: {
  patent: PatentResult;
  onOpenDetail: (p: PatentResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const pub = patent.공개등록공보;
  const pct = Math.round(patent.similarity_score * 100);
  const { text, bg, border } = scoreStyle(pct);
  const appNumClean = pub.application_number.replace(/-/g, "");
  const patentIdClean = pub.patent_id?.replace(/-/g, "") || "";
  // Google Patents는 한국 특허 앞 '10' 접두어를 제외한 번호 사용
  // ex) 1020240168054 → KR20240168054A
  const patentIdForGoogle = patentIdClean.startsWith("10")
    ? patentIdClean.slice(2)
    : patentIdClean;
  const kiprisUrl = `https://doi.org/10.8080/${appNumClean}`;
  const googlePatentsUrl = `https://patents.google.com/patent/KR${patentIdForGoogle}A`;

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      {/* ── 행 클릭 영역 ── */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-5 px-4 py-4 hover:bg-slate-50 transition-colors text-left"
      >
        {/* 좌측: 유사도 + 순위 */}
        <div className={`shrink-0 w-16 flex flex-col items-center justify-center rounded-xl py-2 ${bg} ${border} border`}>
          <span className={`text-xl font-bold leading-none ${text}`}>{pct}%</span>
          <span className="text-xs text-slate-400 mt-0.5">{patent.rank}위</span>
        </div>

        {/* 중앙: 제목 + 메타 */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 hover:text-blue-600 truncate leading-snug">
            {pub.title}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="text-xs text-slate-400">{pub.applicant}</span>
            <span className="text-slate-200 text-xs">|</span>
            <span className="text-xs text-slate-400">{pub.application_date}</span>
            <span className="text-slate-200 text-xs">|</span>
            <StatusBadge status={patent.법적상태.status} isAlive={patent.법적상태.is_alive} />
          </div>
        </div>

        {/* 우측: 아코디언 아이콘 */}
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="shrink-0"
        >
          <ChevronDown className="w-4 h-4 text-gray-400" />
        </motion.div>
      </button>

      {/* ── 아코디언: 초록 + 청구항 ── */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="accordion"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-5 pt-1 ml-[5.25rem] border-l-2 border-blue-100">
              {/* 초록 */}
              <p className="text-sm text-slate-600 leading-relaxed mb-4">
                {pub.abstract}
              </p>

              {/* 청구항 */}
              {pub.claims && pub.claims.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    주요 청구항
                  </p>
                  <ul className="space-y-1">
                    {pub.claims.map((c, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-500">
                        <span className="text-blue-300 mt-0.5 shrink-0">—</span>
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 메타 */}
              <div className="flex items-center gap-4 text-xs text-slate-400 mb-3">
                <span>공개일 {pub.publication_date ?? "미정"}</span>
                <span>출원번호 {pub.application_number}</span>
              </div>

              {/* 외부 링크 + 상세 모달 버튼 */}
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenDetail(patent);
                  }}
                  className="flex items-center justify-center gap-1.5 text-xs font-medium text-indigo-600 border border-indigo-200 bg-indigo-50 hover:bg-indigo-100 rounded-lg px-3 py-2 transition-colors"
                >
                  <Info className="w-3 h-3 shrink-0" />
                  상세 보기
                </button>
                <a
                  href={kiprisUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center justify-center gap-1.5 text-xs font-medium text-blue-600 border border-blue-200 bg-blue-50 hover:bg-blue-100 rounded-lg px-3 py-2 transition-colors"
                >
                  <ExternalLink className="w-3 h-3 shrink-0" />
                  KIPRIS
                </a>
                <a
                  href={googlePatentsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center justify-center gap-1.5 text-xs font-medium text-slate-600 border border-slate-200 bg-slate-50 hover:bg-slate-100 rounded-lg px-3 py-2 transition-colors"
                >
                  <ExternalLink className="w-3 h-3 shrink-0" />
                  Google Patents
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── 리스트 컨테이너 ─────────────────────────── */
interface PatentListProps {
  patents: PatentResult[];
}

export default function PatentList({ patents }: PatentListProps) {
  const [detail, setDetail] = useState<PatentResult | null>(null);

  return (
    <section className="animate-slide-up">
      <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest font-mono mb-3">
        유사 특허 {patents.length}건
      </h2>
      {patents.length === 0 ? (
        <div className="bg-white border border-dashed border-gray-200 rounded-2xl p-8 text-center">
          <p className="text-sm text-slate-500">검색 결과가 없습니다.</p>
          <p className="text-xs text-slate-400 mt-1">
            필터를 완화하거나 다른 키워드로 시도해 보세요.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-sm">
          {patents.map((p) => (
            <PatentRow
              key={p.공개등록공보.application_number}
              patent={p}
              onOpenDetail={setDetail}
            />
          ))}
        </div>
      )}

      <PatentDetailModal patent={detail} onClose={() => setDetail(null)} />
    </section>
  );
}

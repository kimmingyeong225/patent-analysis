"use client";

import { useEffect } from "react";
import { X, ExternalLink } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { PatentResult } from "@/lib/types";
import { buildPatentLinks } from "@/lib/patentUrls";

interface PatentDetailModalProps {
  patent: PatentResult | null;
  onClose: () => void;
}

/**
 * 특허 상세 모달.
 * /search 응답에 이미 포함된 인용문헌 / 법적상태 상세 / 분류코드(IPC·CPC)를
 * 한 화면에서 전부 볼 수 있게 한다 — 백엔드 API 추가 호출 없이 프론트에서 완결.
 */
export default function PatentDetailModal({ patent, onClose }: PatentDetailModalProps) {
  // ESC 키로 닫기 + 배경 스크롤 잠금
  useEffect(() => {
    if (!patent) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [patent, onClose]);

  return (
    <AnimatePresence>
      {patent && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[100] bg-slate-900/40 backdrop-blur-sm flex items-start justify-center px-4 py-10 overflow-y-auto"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label="특허 상세 정보"
        >
          <motion.div
            key="panel"
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl p-6 sm:p-8"
          >
            <DetailBody patent={patent} />
            <button
              type="button"
              onClick={onClose}
              aria-label="상세 모달 닫기"
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ── 모달 본문 ────────────────────────────────── */
function DetailBody({ patent }: { patent: PatentResult }) {
  const pub = patent.공개등록공보;
  const legal = patent.법적상태;
  const cit = patent.인용문헌;
  const codes = patent.분류코드;
  const pct = Math.round(patent.similarity_score * 100);

  const { kiprisUrl, googlePatentsUrl } = buildPatentLinks(pub);

  return (
    <div className="space-y-5">
      {/* 헤더: 유사도·순위·제목 */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-mono text-blue-600 bg-blue-50 border border-blue-100 px-2 py-0.5 rounded">
            {patent.rank}위 · 유사도 {pct}%
          </span>
          <span className="text-xs text-slate-400">{pub.doc_type}</span>
        </div>
        <h3 className="text-lg font-bold text-slate-900 leading-snug pr-8">
          {pub.title}
        </h3>
      </div>

      {/* 메타 그리드 */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <MetaRow label="출원번호" value={pub.application_number} />
        <MetaRow label="출원일" value={pub.application_date} />
        <MetaRow label="출원인" value={pub.applicant} />
        <MetaRow label="발명자" value={pub.inventor} />
        <MetaRow label="공개일" value={pub.publication_date || "—"} />
        <MetaRow label="등록일" value={pub.registration_date || "—"} />
      </dl>

      {/* 초록 */}
      <Section title="초록">
        <p className="text-sm text-slate-600 leading-relaxed">{pub.abstract}</p>
      </Section>

      {/* 청구항 */}
      {pub.claims && pub.claims.length > 0 && (
        <Section title="주요 청구항">
          <ul className="space-y-1.5">
            {pub.claims.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="text-blue-300 mt-0.5 shrink-0">—</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 법적상태 상세 */}
      <Section title="법적상태">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <MetaRow label="상태" value={legal.status} />
          <MetaRow label="상태코드" value={legal.status_code} />
          <MetaRow label="최근 이벤트" value={legal.last_event} />
          <MetaRow label="이벤트일" value={legal.last_event_date || "—"} />
          <MetaRow label="생존 여부" value={legal.is_alive ? "유효" : "소멸"} />
        </div>
      </Section>

      {/* 분류코드 */}
      {(codes.ipc.length > 0 || codes.cpc.length > 0) && (
        <Section title="분류코드">
          {codes.ipc.length > 0 && (
            <CodeBlock label="IPC" items={codes.ipc} />
          )}
          {codes.cpc.length > 0 && (
            <CodeBlock label="CPC" items={codes.cpc} />
          )}
        </Section>
      )}

      {/* 인용문헌 */}
      <Section title="인용문헌">
        <div className="text-sm text-slate-600 space-y-1">
          <p>
            피인용 <b>{cit.cited_by_count}</b>건 · 인용 <b>{cit.citing_count}</b>건
          </p>
          {cit.cited_patents.length > 0 ? (
            <ul className="list-disc list-inside text-slate-500">
              {cit.cited_patents.map((id) => (
                <li key={id} className="font-mono text-xs">{id}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-400">인용 특허 정보 없음</p>
          )}
        </div>
      </Section>

      {/* 외부 링크 */}
      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-100">
        <a
          href={kiprisUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-1.5 text-xs font-medium text-blue-600 border border-blue-200 bg-blue-50 hover:bg-blue-100 rounded-lg px-3 py-2 transition-colors"
        >
          <ExternalLink className="w-3 h-3 shrink-0" />
          KIPRIS에서 보기
        </a>
        <a
          href={googlePatentsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-1.5 text-xs font-medium text-slate-600 border border-slate-200 bg-slate-50 hover:bg-slate-100 rounded-lg px-3 py-2 transition-colors"
        >
          <ExternalLink className="w-3 h-3 shrink-0" />
          Google Patents에서 보기
        </a>
      </div>
    </div>
  );
}

/* ── 소형 헬퍼 컴포넌트 ───────────────────────── */
function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="text-sm text-slate-700 -mt-0.5">{value || "—"}</dd>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
        {title}
      </h4>
      {children}
    </section>
  );
}

function CodeBlock({
  label,
  items,
}: {
  label: string;
  items: { code: string; desc: string }[];
}) {
  return (
    <div className="mb-2 last:mb-0">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <ul className="flex flex-wrap gap-1.5">
        {items.map((c, i) => (
          <li
            key={`${c.code}-${i}`}
            className="inline-flex items-center gap-1 text-xs bg-slate-50 border border-slate-200 rounded px-2 py-0.5"
            title={c.desc}
          >
            <span className="font-mono text-slate-700">{c.code}</span>
            {c.desc && <span className="text-slate-400">· {c.desc}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

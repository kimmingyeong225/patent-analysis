"use client";

import { useState } from "react";
import { SlidersHorizontal, ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import type { SearchFilters } from "@/lib/types";

const CURRENT_YEAR = new Date().getFullYear();

const STATUS_OPTIONS = [
  { value: "",     label: "전체" },
  { value: "등록", label: "등록" },
  { value: "���개", label: "공개" },
  { value: "소멸", label: "소멸" },
];

const RESULT_COUNT_OPTIONS = [5, 10, 15];

const YEAR_PRESETS = [
  { label: "전체", from: null, to: null },
  { label: "최근 3년", from: CURRENT_YEAR - 3, to: CURRENT_YEAR },
  { label: "최근 5년", from: CURRENT_YEAR - 5, to: CURRENT_YEAR },
  { label: "최근 10년", from: CURRENT_YEAR - 10, to: CURRENT_YEAR },
];

interface FilterPanelProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

export default function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false);

  const hasActiveFilter =
    filters.year_from != null ||
    filters.year_to != null ||
    (filters.status != null && filters.status !== "") ||
    (filters.max_results != null && filters.max_results !== 5);

  const activePreset = YEAR_PRESETS.find(
    (p) => p.from === (filters.year_from ?? null) && p.to === (filters.year_to ?? null)
  );

  return (
    <div className="w-full">
      {/* 토글 버튼 */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
          hasActiveFilter
            ? "bg-blue-50 text-blue-600 border-blue-200"
            : "bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-600"
        }`}
      >
        <SlidersHorizontal className="w-3 h-3" />
        고급 검색
        {hasActiveFilter && (
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
        )}
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.15 }}>
          <ChevronDown className="w-3 h-3" />
        </motion.div>
      </button>

      {/* 필터 패널 */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="mt-3 bg-white border border-gray-100 rounded-xl p-4 shadow-sm space-y-4">
              {/* 출원연도 */}
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">
                  출원연도
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {YEAR_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      onClick={() =>
                        onChange({
                          ...filters,
                          year_from: preset.from,
                          year_to: preset.to,
                        })
                      }
                      className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                        activePreset?.label === preset.label
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-slate-500 border-slate-200 hover:border-blue-300"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 법적상태 */}
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">
                  법적상태
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {STATUS_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() =>
                        onChange({ ...filters, status: opt.value || null })
                      }
                      className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                        (filters.status ?? "") === opt.value
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-slate-500 border-slate-200 hover:border-blue-300"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 결과 개��� */}
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">
                  결과 개수
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {RESULT_COUNT_OPTIONS.map((n) => (
                    <button
                      key={n}
                      onClick={() => onChange({ ...filters, max_results: n })}
                      className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
                        (filters.max_results ?? 5) === n
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-slate-500 border-slate-200 hover:border-blue-300"
                      }`}
                    >
                      {n}건
                    </button>
                  ))}
                </div>
              </div>

              {/* 초기화 */}
              {hasActiveFilter && (
                <button
                  onClick={() =>
                    onChange({
                      year_from: null,
                      year_to: null,
                      status: null,
                      max_results: 5,
                    })
                  }
                  className="text-xs text-slate-400 hover:text-red-500 transition-colors"
                >
                  필터 초기화
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

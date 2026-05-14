"use client";

import SearchBar from "./SearchBar";
import FilterPanel from "./FilterPanel";
import type { SearchFilters } from "@/lib/types";

const EXAMPLE_CHIPS = [
  "자가 충전형 스마트 워치 스트랩",
  "AI 기반 의료 영상 진단 시스템",
  "태양광 충전 드론 배터리",
];

interface HomeViewProps {
  onSearch: (query: string) => void;
  filters: SearchFilters;
  onFiltersChange: (filters: SearchFilters) => void;
  history?: string[];
  onRemoveHistory?: (query: string) => void;
  onClearHistory?: () => void;
}

export default function HomeView({
  onSearch,
  filters,
  onFiltersChange,
  history = [],
  onRemoveHistory,
  onClearHistory,
}: HomeViewProps) {
  return (
    <main className="min-h-screen bg-white flex flex-col items-center justify-center px-4">
      {/* 로고 */}
      <div className="mb-10 text-center animate-fade-in">
        <span className="text-4xl">🔬</span>
        <h1 className="mt-3 text-3xl font-bold text-slate-900 tracking-tight">
          PatentAI
        </h1>
        <p className="mt-2 text-slate-400 text-base">
          아이디어를 입력하면 AI가 선행특허를 분석합니다
        </p>
      </div>

      {/* 검색창 + 히스토리 드롭다운 */}
      <div className="w-full max-w-2xl animate-slide-up">
        <SearchBar
          size="hero"
          onSearch={onSearch}
          placeholder="분석할 아이디어를 입력하세요"
          history={history}
          onRemoveHistory={onRemoveHistory}
          onClearHistory={onClearHistory}
        />
      </div>

      {/* 필터 패널 */}
      <div className="mt-4 w-full max-w-2xl flex justify-center animate-fade-in">
        <FilterPanel filters={filters} onChange={onFiltersChange} />
      </div>

      {/* 예시 칩 */}
      <div className="mt-5 flex flex-wrap gap-2 justify-center animate-fade-in">
        <span className="text-sm text-gray-400 self-center">예시</span>
        {EXAMPLE_CHIPS.map((chip) => (
          <button
            key={chip}
            onClick={() => onSearch(chip)}
            className="text-sm text-slate-500 border border-gray-200 bg-white hover:border-blue-300 hover:text-blue-600 px-4 py-1.5 rounded-full transition-colors"
          >
            {chip}
          </button>
        ))}
      </div>
    </main>
  );
}

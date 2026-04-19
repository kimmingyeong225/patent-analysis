"use client";

import SearchBar from "./SearchBar";

interface StickyHeaderProps {
  currentQuery: string;
  onSearch: (query: string) => void;
  onLogoClick: () => void;
  history?: string[];
  onRemoveHistory?: (query: string) => void;
  onClearHistory?: () => void;
}

export default function StickyHeader({
  currentQuery,
  onSearch,
  onLogoClick,
  history = [],
  onRemoveHistory,
  onClearHistory,
}: StickyHeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-100 shadow-sm">
      <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-4">
        {/* 로고 — 클릭 시 홈으로 */}
        <button
          onClick={onLogoClick}
          className="shrink-0 flex items-center gap-1.5 text-slate-800 hover:text-blue-600 font-bold text-base tracking-tight transition-colors"
        >
          <span className="text-xl">🔬</span>
          <span>PatentAI</span>
        </button>

        {/* 검색창 + 히스토리 드롭다운 */}
        <div className="flex-1 max-w-xl">
          <SearchBar
            size="compact"
            initialValue={currentQuery}
            onSearch={onSearch}
            placeholder="다른 아이디어 검색…"
            history={history}
            onRemoveHistory={onRemoveHistory}
            onClearHistory={onClearHistory}
          />
        </div>
      </div>
    </header>
  );
}

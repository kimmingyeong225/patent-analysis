"use client";

import { useState, KeyboardEvent, useRef } from "react";
import { Search, Clock, X } from "lucide-react";

interface SearchBarProps {
  size?: "hero" | "compact";
  initialValue?: string;
  onSearch: (query: string) => void;
  placeholder?: string;
  history?: string[];
  onRemoveHistory?: (query: string) => void;
}

export default function SearchBar({
  size = "hero",
  initialValue = "",
  onSearch,
  placeholder = "분석할 아이디어를 입력하세요",
  history = [],
  onRemoveHistory,
}: SearchBarProps) {
  const [value, setValue]     = useState(initialValue);
  const [focused, setFocused] = useState(false);
  const blurTimer             = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isHero                = size === "hero";

  const handleSubmit = () => {
    const q = value.trim();
    if (q) { onSearch(q); setFocused(false); }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSubmit();
    if (e.key === "Escape") setFocused(false);
  };

  const handleFocus = () => {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    setFocused(true);
  };

  // 드롭다운 클릭이 blur보다 먼저 처리되도록 약간의 딜레이
  const handleBlur = () => {
    blurTimer.current = setTimeout(() => setFocused(false), 150);
  };

  const handleHistoryClick = (q: string) => {
    setValue(q);
    onSearch(q);
    setFocused(false);
  };

  const showDropdown = focused && history.length > 0;

  return (
    <div className="relative w-full">
      {/* ── 검색 입력창 ── */}
      <div
        className={`flex items-center w-full bg-white border rounded-full transition-all ${
          isHero
            ? "border-gray-200 shadow-md focus-within:shadow-lg focus-within:border-blue-300 px-5 py-4 gap-3"
            : "border-gray-200 shadow-sm focus-within:shadow-md focus-within:border-blue-300 px-4 py-2.5 gap-2"
        }`}
      >
        <Search className={`shrink-0 text-gray-400 ${isHero ? "w-5 h-5" : "w-4 h-4"}`} />
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={placeholder}
          className={`flex-1 bg-transparent outline-none text-slate-800 placeholder:text-gray-400 font-sans ${
            isHero ? "text-lg" : "text-sm"
          }`}
          autoFocus={isHero}
        />
        {isHero && value.trim() && (
          <button
            onMouseDown={(e) => e.preventDefault()} // blur 방지
            onClick={handleSubmit}
            className="shrink-0 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2 rounded-full transition-colors"
          >
            분석 시작
          </button>
        )}
      </div>

      {/* ── 히스토리 드롭다운 ── */}
      {showDropdown && (
        <div
          className={`absolute left-0 right-0 bg-white border border-gray-100 rounded-2xl shadow-lg overflow-hidden z-50 ${
            isHero ? "mt-2" : "mt-1.5"
          }`}
        >
          <div className="px-4 py-2 border-b border-gray-50">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              최근 검색
            </span>
          </div>
          {history.map((q) => (
            <div
              key={q}
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors group"
            >
              <Clock className="w-3.5 h-3.5 text-gray-300 shrink-0" />
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleHistoryClick(q)}
                className="flex-1 text-left text-sm text-gray-500 hover:text-slate-700 truncate transition-colors"
              >
                {q}
              </button>
              {onRemoveHistory && (
                <button
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => onRemoveHistory(q)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-300 hover:text-gray-500"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

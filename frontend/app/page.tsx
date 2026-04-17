"use client";

import { useState, useCallback, useRef } from "react";
import HomeView from "@/components/HomeView";
import ResultView from "@/components/ResultView";
import { useSearchHistory } from "@/lib/useSearchHistory";
import { mockPatents, mockAnalysis } from "@/lib/mockData";
import type { PatentResult, Analysis, ViewState, SearchFilters } from "@/lib/types";
import { BACKEND_URL } from "@/lib/constants";

const FETCH_TIMEOUT = 60_000; // 60초
const DEFAULT_FILTERS: SearchFilters = {
  year_from: null,
  year_to: null,
  status: null,
  max_results: 5,
};

/* ── timeout 적용 fetch 헬퍼 ──────────────────── */
async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs = FETCH_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/* ── 1단계: 특허 검색 (필터 포함) ─────────────── */
async function fetchPatents(
  query: string,
  filters: SearchFilters
): Promise<PatentResult[]> {
  if (!BACKEND_URL) {
    await new Promise((r) => setTimeout(r, 800));
    return mockPatents;
  }

  const body: Record<string, unknown> = { query };
  if (filters.year_from != null) body.year_from = filters.year_from;
  if (filters.year_to != null) body.year_to = filters.year_to;
  if (filters.status) body.status = filters.status;
  if (filters.max_results != null) body.max_results = filters.max_results;

  const res = await fetchWithTimeout(`${BACKEND_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Search API failed: ${res.statusText}`);
  const data = await res.json();
  return data.results;
}

/* ── 2단계: AI 분석 (별도 호출) ───────────────── */
async function fetchAnalysis(
  query: string,
  patents: PatentResult[]
): Promise<Analysis> {
  if (!BACKEND_URL || patents.length === 0) {
    await new Promise((r) => setTimeout(r, 400));
    return mockAnalysis;
  }

  const res = await fetchWithTimeout(`${BACKEND_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_idea: query, patents }),
  });
  if (!res.ok) throw new Error(`Analyze API failed: ${res.statusText}`);
  return await res.json();
}

/* ── 로딩 화면 (검색 중) ──────────────────────── */
function LoadingView({ query }: { query: string }) {
  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-6">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm">
          <span className="font-semibold text-slate-700">&quot;{query}&quot;</span> 유사 특허 검색 중…
        </p>
      </div>
    </div>
  );
}

/* ── 메인 페이지 ─────────────────────────────── */
export default function Page() {
  const [view, setView] = useState<ViewState>("home");
  const [query, setQuery] = useState("");
  const [patents, setPatents] = useState<PatentResult[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);

  const { history, add: addToHistory, remove: removeFromHistory } = useSearchHistory();

  const analyzeAbort = useRef<AbortController | null>(null);

  const handleSearch = useCallback(async (q: string) => {
    analyzeAbort.current?.abort();

    setQuery(q);
    setView("loading");
    setAnalysis(null);
    setAnalyzing(false);
    addToHistory(q);

    /* ── 1단계: 검색 (필터 적용) ── */
    let searchedPatents: PatentResult[];
    try {
      searchedPatents = await fetchPatents(q, filters);
    } catch (err) {
      console.error("Search failed:", err);
      searchedPatents = mockPatents;
    }

    setPatents(searchedPatents);
    setView("results");

    /* ── 2단계: 분석 (백그라운드) ── */
    setAnalyzing(true);
    const controller = new AbortController();
    analyzeAbort.current = controller;

    try {
      const result = await fetchAnalysis(q, searchedPatents);
      if (!controller.signal.aborted) {
        setAnalysis(result);
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        console.error("Analyze failed:", err);
        setAnalysis(mockAnalysis);
      }
    } finally {
      if (!controller.signal.aborted) {
        setAnalyzing(false);
      }
    }
  }, [addToHistory, filters]);

  const handleHome = useCallback(() => setView("home"), []);

  if (view === "home") {
    return (
      <HomeView
        onSearch={handleSearch}
        filters={filters}
        onFiltersChange={setFilters}
        history={history}
        onRemoveHistory={removeFromHistory}
      />
    );
  }

  if (view === "loading") return <LoadingView query={query} />;

  return (
    <ResultView
      query={query}
      patents={patents}
      analysis={analysis}
      analyzing={analyzing}
      onSearch={handleSearch}
      onHome={handleHome}
      history={history}
      onRemoveHistory={removeFromHistory}
    />
  );
}

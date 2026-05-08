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
// 외부 signal(사용자 취소)과 내부 timeout signal을 합성하여
// 어느 쪽이든 abort되면 fetch가 즉시 중단되도록 함.
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs = FETCH_TIMEOUT
): Promise<Response> {
  const timeoutController = new AbortController();
  const timer = setTimeout(() => timeoutController.abort(), timeoutMs);

  const externalSignal = options.signal ?? null;

  // 이미 외부에서 취소된 상태면 즉시 중단
  if (externalSignal?.aborted) {
    clearTimeout(timer);
    throw new DOMException("Aborted", "AbortError");
  }

  let signal: AbortSignal;
  let cleanup: (() => void) | null = null;

  if (externalSignal) {
    // AbortSignal.any 지원 환경(최신 브라우저/Node 20+) — 우선 사용
    const anyFn = (AbortSignal as unknown as {
      any?: (signals: AbortSignal[]) => AbortSignal;
    }).any;
    if (typeof anyFn === "function") {
      signal = anyFn([externalSignal, timeoutController.signal]);
    } else {
      // 폴백: 외부 abort 시 timeoutController를 수동으로 abort
      const onAbort = () => timeoutController.abort();
      externalSignal.addEventListener("abort", onAbort, { once: true });
      cleanup = () => externalSignal.removeEventListener("abort", onAbort);
      signal = timeoutController.signal;
    }
  } else {
    signal = timeoutController.signal;
  }

  try {
    return await fetch(url, { ...options, signal });
  } finally {
    clearTimeout(timer);
    cleanup?.();
  }
}

/* ── 1단계: 특허 검색 (필터 포함) ─────────────── */
async function fetchPatents(
  query: string,
  filters: SearchFilters,
  signal?: AbortSignal
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
    signal,
  });
  if (!res.ok) throw new Error(`Search API failed: ${res.statusText}`);
  const data = await res.json();
  return data.results;
}

/* ── 2단계: AI 분석 (별도 호출) ───────────────── */
async function fetchAnalysis(
  query: string,
  patents: PatentResult[],
  signal?: AbortSignal
): Promise<Analysis> {
  if (!BACKEND_URL || patents.length === 0) {
    await new Promise((r) => setTimeout(r, 400));
    return mockAnalysis;
  }

  const res = await fetchWithTimeout(`${BACKEND_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_idea: query, patents }),
    signal,
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
  // 검색/분석 단계별 에러 메시지 — 성공 시 null. mock 폴백 시에도 사용자에게 명시.
  const [searchError, setSearchError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const { history, add: addToHistory, remove: removeFromHistory, clear: clearHistory } =
    useSearchHistory();

  const searchAbort = useRef<AbortController | null>(null);
  const analyzeAbort = useRef<AbortController | null>(null);

  const handleSearch = useCallback(async (q: string) => {
    searchAbort.current?.abort();
    analyzeAbort.current?.abort();

    setQuery(q);
    setView("loading");
    setAnalysis(null);
    setAnalyzing(false);
    setSearchError(null);
    setAnalysisError(null);
    addToHistory(q);

    /* ── 1단계: 검색 (필터 적용) ── */
    const searchController = new AbortController();
    searchAbort.current = searchController;

    let searchedPatents: PatentResult[];
    try {
      searchedPatents = await fetchPatents(q, filters, searchController.signal);
      if (searchController.signal.aborted) return;
    } catch (err) {
      // 사용자가 취소한 경우(새 검색/홈 클릭)는 폴백 없이 조용히 무시 — 비용 낭비 방지
      const name = (err as { name?: string } | null)?.name;
      if (searchController.signal.aborted || name === "AbortError") {
        return;
      }
      console.error("Search failed:", err);
      searchedPatents = mockPatents;
      setSearchError(
        "특허 검색 API 호출에 실패했습니다. 샘플 데이터로 대체해 표시합니다."
      );
    }

    setPatents(searchedPatents);
    setView("results");

    /* ── 2단계: 분석 (백그라운드) ── */
    setAnalyzing(true);
    const controller = new AbortController();
    analyzeAbort.current = controller;

    try {
      const result = await fetchAnalysis(q, searchedPatents, controller.signal);
      if (!controller.signal.aborted) {
        setAnalysis(result);
      }
    } catch (err) {
      // 사용자가 취소한 경우(새 검색/홈 클릭)는 폴백 없이 조용히 무시 — 비용 낭비 방지
      const name = (err as { name?: string } | null)?.name;
      if (controller.signal.aborted || name === "AbortError") {
        return;
      }
      console.error("Analyze failed:", err);
      setAnalysis(mockAnalysis);
      setAnalysisError(
        "AI 분석 API 호출에 실패했습니다. 샘플 분석으로 대체해 표시합니다."
      );
    } finally {
      if (!controller.signal.aborted) {
        setAnalyzing(false);
      }
    }
  }, [addToHistory, filters]);

  const handleHome = useCallback(() => {
    // 진행 중인 검색/분석이 있으면 즉시 취소 — view 강제 전환 + GPT-4o 불필요 호출 방지
    searchAbort.current?.abort();
    searchAbort.current = null;
    analyzeAbort.current?.abort();
    analyzeAbort.current = null;
    setAnalyzing(false);
    setView("home");
    setSearchError(null);
    setAnalysisError(null);
  }, []);

  if (view === "home") {
    return (
      <HomeView
        onSearch={handleSearch}
        filters={filters}
        onFiltersChange={setFilters}
        history={history}
        onRemoveHistory={removeFromHistory}
        onClearHistory={clearHistory}
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
      searchError={searchError}
      analysisError={analysisError}
      onDismissSearchError={() => setSearchError(null)}
      onDismissAnalysisError={() => setAnalysisError(null)}
      onSearch={handleSearch}
      onHome={handleHome}
      history={history}
      onRemoveHistory={removeFromHistory}
      onClearHistory={clearHistory}
    />
  );
}

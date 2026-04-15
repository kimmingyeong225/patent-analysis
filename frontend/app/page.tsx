"use client";

import { useState, useCallback } from "react";
import HomeView from "@/components/HomeView";
import ResultView from "@/components/ResultView";
import { useSearchHistory } from "@/lib/useSearchHistory";
import type { PatentResult, Analysis, ViewState } from "@/lib/types";

const BACKEND_URL = "http://localhost:8000";

/* ── API 호출 ─────── */
async function fetchResults(
  query: string
): Promise<{ patents: PatentResult[]; analysis: Analysis | null }> {
  // 1. 특허 검색 (/search)
  const searchRes = await fetch(`${BACKEND_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  
  if (!searchRes.ok) throw new Error("Search API failed");
  const searchData = await searchRes.json();
  const patents = searchData.results;

  // 검색 결과가 없으면 분석을 건너뜀
  if (!patents || patents.length === 0) {
    return { patents: [], analysis: null };
  }

  // 2. AI 분석 (/analyze) - 상위 5개 특허 기준
  try {
    const analyzeRes = await fetch(`${BACKEND_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        user_idea: query, 
        patents: patents.slice(0, 5) 
      }),
    });

    if (!analyzeRes.ok) {
        console.warn("Analysis API failed");
        return { patents, analysis: null };
    }

    const analysis = await analyzeRes.json();
    return { patents, analysis };
  } catch (err) {
    console.error("Analysis error:", err);
    return { patents, analysis: null };
  }
}

/* ── 로딩 화면 ──────────────────────────────── */
function LoadingView({ query }: { query: string }) {
  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-6">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm">
          <span className="font-semibold text-slate-700">"{query}"</span> 분석 중…
        </p>
      </div>
      <ol className="text-xs text-slate-400 space-y-1 text-center list-none">
        <li>🔍 유사 특허 데이터베이스 검색 중</li>
        <li>🤖 GPT-4o 신규성 분석 중</li>
        <li>📊 결과 정리 중</li>
      </ol>
    </div>
  );
}

/* ── 메인 페이지 ─────────────────────────────── */
export default function Page() {
  const [view, setView]         = useState<ViewState>("home");
  const [query, setQuery]       = useState("");
  const [patents, setPatents]   = useState<PatentResult[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError]       = useState<string | null>(null);

  const { history, add: addToHistory, remove: removeFromHistory } = useSearchHistory();

  const handleSearch = useCallback(async (q: string) => {
    setQuery(q);
    setView("loading");
    setError(null);
    addToHistory(q);

    try {
      const result = await fetchResults(q);
      setPatents(result.patents);
      setAnalysis(result.analysis);
      setView("results");
    } catch (err) {
      console.error(err);
      setError("검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
      setView("results");
    }
  }, [addToHistory]);

  const handleHome = useCallback(() => {
    setView("home");
    setError(null);
  }, []);

  if (view === "home") {
    return (
      <HomeView
        onSearch={handleSearch}
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
      error={error}
      onSearch={handleSearch}
      onHome={handleHome}
      history={history}
      onRemoveHistory={removeFromHistory}
    />
  );
}

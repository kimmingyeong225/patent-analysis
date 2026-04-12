"use client";

import { useState, useCallback } from "react";
import HomeView from "@/components/HomeView";
import ResultView from "@/components/ResultView";
import { useSearchHistory } from "@/lib/useSearchHistory";
import { mockPatents, mockAnalysis } from "@/lib/mockData";
import type { PatentResult, Analysis, ViewState } from "@/lib/types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

/* ── API 호출 (BACKEND_URL 없으면 mock) ─────── */
async function fetchResults(
  query: string
): Promise<{ patents: PatentResult[]; analysis: Analysis }> {
  if (!BACKEND_URL) {
    await new Promise((r) => setTimeout(r, 1200));
    return { patents: mockPatents, analysis: mockAnalysis };
  }
  const res = await fetch(`${BACKEND_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = await res.json();
  return { patents: data.results, analysis: mockAnalysis }; // TODO: 분석 엔드포인트 연동
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

  const { history, add: addToHistory, remove: removeFromHistory } = useSearchHistory();

  const handleSearch = useCallback(async (q: string) => {
    setQuery(q);
    setView("loading");
    addToHistory(q);                     // 히스토리에 저장

    try {
      const result = await fetchResults(q);
      setPatents(result.patents);
      setAnalysis(result.analysis);
      setView("results");
    } catch (err) {
      console.error(err);
      setPatents(mockPatents);
      setAnalysis(mockAnalysis);
      setView("results");
    }
  }, [addToHistory]);

  const handleHome = useCallback(() => setView("home"), []);

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
      analysis={analysis!}
      onSearch={handleSearch}
      onHome={handleHome}
      history={history}
      onRemoveHistory={removeFromHistory}
    />
  );
}

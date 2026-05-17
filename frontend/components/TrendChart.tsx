"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  BarChart, Bar,
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import type { TooltipProps } from "recharts";
import { Search, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { BACKEND_URL } from "@/lib/constants";

type TrendPoint = { year: string; count: number };
type ChartType = "막대" | "라인";

/* ── 커스텀 툴팁 ─────────────────────────────── */
function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-100 rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-semibold text-slate-700 mb-0.5">{label}년</p>
      <p className="text-blue-600 font-mono">{payload[0].value?.toLocaleString() ?? "—"}건</p>
    </div>
  );
}

/* ── 지표 카드 ───────────────────────────────── */
function MetricCard({
  label, value, sub,
}: {
  label: string;
  value: string;
  sub?: React.ReactNode;
}) {
  return (
    <div className="bg-slate-50 border border-gray-100 rounded-xl px-4 py-3">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-lg font-bold text-slate-800 leading-none">{value}</p>
      {sub && <div className="mt-1">{sub}</div>}
    </div>
  );
}

/* ── 컴포넌트 ────────────────────────────────── */
interface TrendChartProps {
  initialKeyword: string;
}

export default function TrendChart({ initialKeyword }: TrendChartProps) {
  const [keyword, setKeyword]     = useState(initialKeyword);
  const [displayed, setDisplayed] = useState(initialKeyword);
  const [data, setData]           = useState<TrendPoint[]>([]);
  const [isTruncated, setIsTruncated] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [fetchError, setFetchError] = useState(false);
  const [chartType, setChartType] = useState<ChartType>("막대");
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchTrend = useCallback(async (kw: string) => {
    const trimmed = kw.trim();
    if (!trimmed) return;

    // 진행 중인 요청 취소 — 늦게 도착한 응답이 최신 응답을 덮어쓰는 race 방지
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setFetchError(false);
    try {
      const res = await fetch(
        `${BACKEND_URL}/trend?query=${encodeURIComponent(trimmed)}`,
        { signal: controller.signal }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (controller.signal.aborted) return;
      setData(json.trend_data ?? []);
      setIsTruncated(json.is_truncated ?? false);
      setDisplayed(trimmed);
    } catch (e) {
      // abort 는 race 방지 의도 — 조용히 무시 (page.tsx fetchAnalysis 와 동일 패턴)
      const name = (e as { name?: string } | null)?.name;
      if (controller.signal.aborted || name === "AbortError") {
        return;
      }
      console.error("Trend fetch error:", e);
      setData([]);
      setFetchError(true);
    } finally {
      // 새 fetch 가 setLoading(true) 를 이미 호출했으므로 abort 된 경우 덮어쓰지 않음
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    setKeyword(initialKeyword);
    fetchTrend(initialKeyword);
    return () => {
      abortRef.current?.abort();
    };
  }, [initialKeyword, fetchTrend]);

  const handleSearch = () => fetchTrend(keyword);

  /* ── 지표 계산 ── */
  const totalCount = data.reduce((s, d) => s + d.count, 0);
  const maxItem    = data.length > 0
    ? data.reduce((m, d) => (d.count > m.count ? d : m), data[0])
    : null;
  const sorted  = [...data].sort((a, b) => a.year.localeCompare(b.year));
  const lastTwo = sorted.slice(-2);
  const yoy = lastTwo.length === 2 && lastTwo[0].count > 0
    ? ((lastTwo[1].count - lastTwo[0].count) / lastTwo[0].count) * 100
    : null;

  const yoyLabel =
    yoy === null ? "–" :
    yoy > 0      ? `+${yoy.toFixed(1)}%` :
    yoy < 0      ? `${yoy.toFixed(1)}%` : "0%";

  const YoyIcon =
    yoy === null ? Minus :
    yoy > 0      ? TrendingUp : TrendingDown;

  const yoyColor =
    yoy === null ? "text-slate-400" :
    yoy > 0      ? "text-green-500" : "text-red-500";

  /* 막대 색상 — 최고 연도 강조 */
  const barFill = (year: string) =>
    year === maxItem?.year ? "#185FA5" : "#85B7EB";

  const commonAxis = {
    axisLine: false,
    tickLine: false,
  };

  return (
    <section className="animate-slide-up">
      <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest font-mono mb-3">
        📈 연도별 특허 출원 트렌드
      </h2>

      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5 space-y-5">
        {/* 검색 입력 */}
        <div className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 bg-slate-50 border border-gray-200 rounded-full px-4 py-2 focus-within:border-blue-300 transition-colors">
            <Search className="w-3.5 h-3.5 text-gray-400 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="트렌드를 분석할 키워드를 입력하세요"
              className="flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-gray-400"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="shrink-0 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-4 py-2 rounded-full transition-colors"
          >
            {loading ? "조회 중…" : "조회"}
          </button>
        </div>

        {/* 로딩 */}
        {loading && (
          <div className="flex items-center justify-center h-[220px]">
            <div className="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          </div>
        )}

        {/* 백엔드 오류 */}
        {!loading && fetchError && (
          <div className="flex items-center justify-center h-[100px] text-slate-400 text-sm text-center">
            트렌드 데이터를 불러올 수 없습니다. 백엔드 연동 후 사용 가능합니다.
          </div>
        )}

        {/* 데이터 없음 */}
        {!loading && !fetchError && data.length === 0 && (
          <div className="flex flex-col items-center justify-center h-[100px] gap-1 text-slate-400 text-sm">
            <span>출원일 정보가 있는 특허 데이터가 없습니다.</span>
            <span className="text-xs">KIPRIS API가 출원일을 제공한 특허에 한해 집계됩니다.</span>
          </div>
        )}

        {/* 데이터 있을 때 */}
        {!loading && data.length > 0 && (
          <>
            {/* 지표 3개 */}
            <div className="grid grid-cols-3 gap-3">
              <MetricCard
                label="총 출원 건수"
                value={isTruncated ? `${totalCount.toLocaleString()}건+` : `${totalCount.toLocaleString()}건`}
              />
              <MetricCard
                label="최고 출원 연도"
                value={`${maxItem?.year ?? "–"}년`}
                sub={
                  <span className="text-xs text-slate-400 font-mono">
                    {maxItem?.count.toLocaleString()}건
                  </span>
                }
              />
              <MetricCard
                label="YoY 증감률"
                value={yoyLabel}
                sub={
                  yoy !== null && (
                    <span className={`flex items-center gap-0.5 text-xs ${yoyColor}`}>
                      <YoyIcon className="w-3 h-3" />
                      {lastTwo[0].year} → {lastTwo[1].year}
                    </span>
                  )
                }
              />
            </div>

            {/* 차트 타입 토글 */}
            <div className="flex items-center gap-2">
              {(["막대", "라인"] as ChartType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setChartType(type)}
                  className={`text-xs font-medium px-3.5 py-1.5 rounded-full border transition-all ${
                    chartType === type
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-600"
                  }`}
                >
                  {type} 그래프
                </button>
              ))}
              <span className="ml-auto text-xs text-slate-400 font-mono">
                <span className="font-semibold text-slate-600">"{displayed}"</span> 기준
              </span>
            </div>

            {/* 차트 */}
            <ResponsiveContainer width="100%" height={200}>
              {chartType === "막대" ? (
                <BarChart data={data} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="0" stroke="#f1f5f9" vertical={false} />
                  <XAxis
                    dataKey="year"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    {...commonAxis}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#cbd5e1" }}
                    tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v)}
                    label={{ value: "출원 건수", angle: -90, position: "insideLeft", offset: 15, style: { fontSize: 10, fill: "#94a3b8" } }}
                    allowDecimals={false}
                    {...commonAxis}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={false} />
                  <Bar dataKey="count" radius={[5, 5, 0, 0]}>
                    {data.map((d, i) => (
                      <Cell key={`cell-${i}`} fill={barFill(d.year)} />
                    ))}
                  </Bar>
                </BarChart>
              ) : (
                <LineChart data={data} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="0" stroke="#f1f5f9" vertical={false} />
                  <XAxis
                    dataKey="year"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    {...commonAxis}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#cbd5e1" }}
                    tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v)}
                    label={{ value: "출원 건수", angle: -90, position: "insideLeft", offset: 15, style: { fontSize: 10, fill: "#94a3b8" } }}
                    allowDecimals={false}
                    {...commonAxis}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#185FA5"
                    strokeWidth={2}
                    dot={{ fill: "#185FA5", r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: "#185FA5" }}
                  />
                </LineChart>
              )}
            </ResponsiveContainer>
          </>
        )}
      </div>
    </section>
  );
}

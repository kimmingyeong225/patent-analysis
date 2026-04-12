"use client";

import { useState, useRef } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Search } from "lucide-react";

/* ── 목 데이터 생성 ────────────────────────────────────────────
   키워드별로 살짝 다른 값을 돌려주기 위해 문자열 길이를 seed로 사용
   (Math.random 대신 결정적 계산 → hydration 오류 방지)
──────────────────────────────────────────────────────────────── */
const BASE = [1240, 1580, 1920, 2340, 2780, 3120];
const YEARS = ["2019", "2020", "2021", "2022", "2023", "2024"];

function buildTrendData(keyword: string) {
  const seed = keyword.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return YEARS.map((year, i) => ({
    year,
    count: Math.round(BASE[i] * (0.75 + ((seed * (i + 1)) % 50) / 100)),
  }));
}

/* ── 커스텀 툴팁 ─────────────────────────────── */
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-100 rounded-lg px-3 py-2 shadow-lg text-sm">
      <p className="font-semibold text-slate-700 mb-0.5">{label}년</p>
      <p className="text-blue-600 font-mono">{payload[0].value.toLocaleString()}건</p>
    </div>
  );
}

/* ── 컴포넌트 ────────────────────────────────── */
interface TrendChartProps {
  initialKeyword: string;
}

export default function TrendChart({ initialKeyword }: TrendChartProps) {
  const [keyword, setKeyword]   = useState(initialKeyword);
  const [displayed, setDisplayed] = useState(initialKeyword);
  const [data, setData]         = useState(() => buildTrendData(initialKeyword));
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = () => {
    const kw = keyword.trim();
    if (!kw) return;
    setData(buildTrendData(kw));
    setDisplayed(kw);
    setActiveIdx(null);
  };

  const maxCount = Math.max(...data.map((d) => d.count));

  return (
    <section className="animate-slide-up">
      {/* 섹션 헤더 */}
      <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest font-mono mb-3">
        📈 연도별 특허 출원 트렌드
      </h2>

      <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5">
        {/* 검색 입력 */}
        <div className="flex items-center gap-2 mb-5">
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
            className="shrink-0 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-full transition-colors"
          >
            조회
          </button>
        </div>

        {/* 차트 제목 */}
        <p className="text-xs text-slate-400 mb-3 font-mono">
          <span className="text-slate-600 font-semibold">"{displayed}"</span> 키워드 연도별 출원 건수
        </p>

        {/* Recharts 막대 그래프 */}
        <ResponsiveContainer width="100%" height={200}>
          <BarChart
            data={data}
            margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
            onMouseLeave={() => setActiveIdx(null)}
          >
            <CartesianGrid
              strokeDasharray="0"
              stroke="#f1f5f9"
              vertical={false}
            />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 11, fill: "#94a3b8", fontFamily: "IBM Plex Mono" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#cbd5e1", fontFamily: "IBM Plex Mono" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
            />
            <Tooltip content={<CustomTooltip />} cursor={false} />
            <Bar
              dataKey="count"
              radius={[5, 5, 0, 0]}
              onMouseEnter={(_, idx) => setActiveIdx(idx)}
            >
              {data.map((_, idx) => (
                <Cell
                  key={`cell-${idx}`}
                  fill={activeIdx === idx ? "#1d4ed8" : "#3b82f6"}
                  opacity={activeIdx !== null && activeIdx !== idx ? 0.5 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* 최고점 표시 */}
        <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-400">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" />
          최고 출원 연도:{" "}
          <span className="font-semibold text-slate-600 font-mono">
            {data.find((d) => d.count === maxCount)?.year}년 ({maxCount.toLocaleString()}건)
          </span>
        </div>
      </div>
    </section>
  );
}

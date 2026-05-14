import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PatentAI | 특허 신규성 분석기",
  description: "AI 기반 특허 신규성 분석 시스템 — 아이디어를 입력하면 선행특허를 즉시 분석합니다",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

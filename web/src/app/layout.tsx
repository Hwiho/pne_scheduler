import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PNE 스케줄 워크스페이스",
  description: "설정 → 프로토콜·실행 순서 → 내보내기 · 고온저장 추적",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PNE 스케줄 워크스페이스",
  description: "설정 → 프로토콜 → 절차 → 검증 → 내보내기",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

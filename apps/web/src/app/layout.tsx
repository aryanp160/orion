import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ORION // Quantitative Execution Intelligence Terminal",
  description: "On-chain Routing & Intelligence for Optimal Notional Execution in Ethereum Perpetual Futures",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark bg-[#0B0E14] text-[#E2E8F0]">
      <body className="min-h-screen bg-[#0B0E14] text-[#E2E8F0] antialiased selection:bg-[#3B82F6]/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}

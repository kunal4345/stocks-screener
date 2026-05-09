import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stocks to Buy Now",
  description: "Simple stock screener - what to buy and hold today",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-black">{children}</body>
    </html>
  );
}

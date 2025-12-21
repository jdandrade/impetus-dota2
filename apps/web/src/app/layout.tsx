import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Impetus | Dota 2 Performance Analytics",
  description:
    "Next-generation Dota 2 performance analytics platform. Analyze your matches with the OpenIMP scoring engine.",
  keywords: ["dota 2", "analytics", "performance", "imp score", "stratz alternative"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-cyber-bg`}
      >
        {children}
      </body>
    </html>
  );
}

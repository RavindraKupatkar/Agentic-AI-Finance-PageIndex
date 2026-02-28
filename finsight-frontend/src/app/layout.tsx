import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FinSight AI — Finance Document Intelligence",
  description: "Upload financial PDFs and get AI-powered answers with citations. Built with LangGraph + PageIndex.",
};

import { BackgroundVignette } from "@/components/BackgroundVignette";

import ConvexClientProvider from "@/components/convex-client-provider";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        <ConvexClientProvider>
          <BackgroundVignette />
          {children}
        </ConvexClientProvider>
      </body>
    </html>
  );
}

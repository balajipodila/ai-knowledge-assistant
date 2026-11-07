import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/components/auth-provider";
import { ThemeColorMeta } from "@/components/theme-color-meta";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-cosmos",
});

export const metadata: Metadata = {
  title: {
    default: "AI Knowledge Assistant",
    template: "%s | AI Knowledge Assistant",
  },
  description:
    "Ask questions about your PDFs and explore answers grounded in retrieved passages.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#0a1628",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <ThemeColorMeta />
        <div className="cloud-layer" aria-hidden="true" />
        <div className="lightning-flash" aria-hidden="true" />
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lumina",
  description: "DDL and torrent content download orchestrator",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="cs" className="dark">
      <body className="min-h-screen antialiased">
        <nav className="border-b border-zinc-800/50 px-4 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <Link
              href="/"
              className="text-lg font-bold bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent"
            >
              Lumina
            </Link>
            <Link
              href="/settings"
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Nastavení
            </Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}

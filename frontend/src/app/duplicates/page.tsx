"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  DuplicateGroup,
  DuplicateFile,
  scanDuplicates,
  aiScanDuplicates,
  getDuplicates,
  deleteDuplicateFile,
  formatSize,
} from "@/lib/api";
import DownloadPanel from "@/components/DownloadPanel";

type ScanMode = "simple" | "ai";

export default function DuplicatesPage() {
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanType, setScanType] = useState<ScanMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [activeMode, setActiveMode] = useState<ScanMode>("simple");

  useEffect(() => {
    loadDuplicates("simple");
  }, []);

  async function loadDuplicates(mode: ScanMode) {
    setLoading(true);
    setError(null);
    try {
      const data = await getDuplicates(mode);
      setGroups(data.groups);
      setActiveMode(mode);
      setExpandedGroups(new Set(data.groups.map((g) => groupKey(g))));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chyba pri nacitani");
    } finally {
      setLoading(false);
    }
  }

  async function handleScan() {
    setScanning(true);
    setScanType("simple");
    setError(null);
    setScanResult(null);
    try {
      const result = await scanDuplicates();
      setScanResult(
        `Proskenovano ${result.scanned} souboru v ${result.media_dir}`
      );
      await loadDuplicates("simple");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan selhal");
    } finally {
      setScanning(false);
      setScanType(null);
    }
  }

  async function handleAiScan() {
    setScanning(true);
    setScanType("ai");
    setError(null);
    setScanResult(null);
    try {
      const result = await aiScanDuplicates();
      setScanResult(
        `AI proskenovalo ${result.scanned} souboru, nalezeno ${result.ai_groups} skupin duplicit`
      );
      await loadDuplicates("ai");
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI scan selhal");
    } finally {
      setScanning(false);
      setScanType(null);
    }
  }

  async function handleDelete(file: DuplicateFile, group: DuplicateGroup) {
    if (
      !confirm(
        `Opravdu smazat "${file.filename}"?\n\nSoubor bude trvale odstranen z disku.`
      )
    )
      return;

    setDeleting(file.id);
    try {
      await deleteDuplicateFile(file.id);
      setGroups((prev) =>
        prev
          .map((g) => {
            if (g.title === group.title) {
              return {
                ...g,
                files: g.files.filter((f) => f.id !== file.id),
                count: g.count - 1,
              };
            }
            return g;
          })
          .filter((g) => g.count > 1)
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Smazani selhalo");
    } finally {
      setDeleting(null);
    }
  }

  function groupKey(g: DuplicateGroup) {
    return g.title;
  }

  function toggleGroup(g: DuplicateGroup) {
    const key = groupKey(g);
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function formatDate(iso: string) {
    if (!iso) return "-";
    try {
      return new Date(iso).toLocaleDateString("cs-CZ", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return iso;
    }
  }

  const qualityColor: Record<string, string> = {
    "2160p": "bg-amber-600/20 text-amber-400 border-amber-700",
    "1080p": "bg-violet-600/20 text-violet-400 border-violet-700",
    "720p": "bg-blue-600/20 text-blue-400 border-blue-700",
    "480p": "bg-zinc-600/20 text-zinc-400 border-zinc-700",
    unknown: "bg-zinc-800/50 text-zinc-500 border-zinc-700",
  };

  const spinnerSvg = (
    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );

  return (
    <main className="flex flex-col gap-6 px-4 py-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="text-zinc-500 hover:text-zinc-300 transition-colors text-sm"
          >
            &larr; Hledat
          </Link>
          <h1 className="text-2xl font-bold text-zinc-100">Duplicity</h1>
          {activeMode === "ai" && !loading && groups.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-fuchsia-900/30 text-fuchsia-400 border border-fuchsia-800">
              AI
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium transition-colors"
          >
            {scanning && scanType === "simple" ? (
              <span className="flex items-center gap-2">
                {spinnerSvg}
                Skenuji...
              </span>
            ) : (
              "Skenovat"
            )}
          </button>
          <button
            onClick={handleAiScan}
            disabled={scanning}
            className="px-4 py-2 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium transition-colors"
          >
            {scanning && scanType === "ai" ? (
              <span className="flex items-center gap-2">
                {spinnerSvg}
                AI skenuje...
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                AI skenovat
              </span>
            )}
          </button>
        </div>
      </div>

      {scanResult && (
        <div className="rounded-lg bg-emerald-900/30 border border-emerald-800 px-4 py-3 text-emerald-300 text-sm">
          {scanResult}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-900/30 border border-red-800 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-zinc-500 animate-pulse text-center py-12">
          Nacitam...
        </div>
      ) : groups.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <div className="text-zinc-600 text-4xl">&#10003;</div>
          <p className="text-zinc-400">Zadne duplicity nenalezeny</p>
          <p className="text-zinc-600 text-sm">
            Klikni &quot;Skenovat&quot; pro rychle hledani nebo &quot;AI
            skenovat&quot; pro chytre hledani (vcetne prelozenych nazvu)
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-zinc-500 text-sm">
            {groups.length} skupin duplicit &middot;{" "}
            {groups.reduce((sum, g) => sum + g.count, 0)} souboru celkem
          </p>

          {groups.map((group) => {
            const key = groupKey(group);
            const expanded = expandedGroups.has(key);
            const totalSize = group.files.reduce((s, f) => s + f.size, 0);

            return (
              <div
                key={key}
                className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden"
              >
                <button
                  onClick={() => toggleGroup(group)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <svg
                      className={`w-4 h-4 text-zinc-500 transition-transform ${
                        expanded ? "rotate-90" : ""
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                    <span className="font-medium text-zinc-100">
                      {group.title}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
                      {group.count} souboru
                    </span>
                  </div>
                  <span className="text-sm text-zinc-500">
                    {formatSize(totalSize)}
                  </span>
                </button>

                {expanded && (
                  <div className="border-t border-zinc-800">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-zinc-500 text-xs uppercase tracking-wider">
                          <th className="text-left px-4 py-2 font-medium">
                            Soubor
                          </th>
                          <th className="text-center px-2 py-2 font-medium w-20">
                            Kvalita
                          </th>
                          <th className="text-center px-2 py-2 font-medium w-16">
                            Jazyk
                          </th>
                          <th className="text-right px-2 py-2 font-medium w-24">
                            Velikost
                          </th>
                          <th className="text-right px-2 py-2 font-medium w-28">
                            Datum
                          </th>
                          <th className="px-4 py-2 w-12" />
                        </tr>
                      </thead>
                      <tbody>
                        {group.files.map((file, idx) => (
                          <tr
                            key={file.id}
                            className={`border-t border-zinc-800/50 hover:bg-zinc-800/30 ${
                              idx === 0 ? "bg-zinc-800/20" : ""
                            }`}
                          >
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-2">
                                {idx === 0 && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-900/30 text-emerald-400 border border-emerald-800 whitespace-nowrap">
                                    Nejvetsi
                                  </span>
                                )}
                                <span
                                  className="text-zinc-300 truncate max-w-md"
                                  title={file.path}
                                >
                                  {file.filename}
                                </span>
                              </div>
                            </td>
                            <td className="text-center px-2 py-2.5">
                              <span
                                className={`text-xs px-2 py-0.5 rounded-full border ${
                                  qualityColor[file.quality] ||
                                  qualityColor.unknown
                                }`}
                              >
                                {file.quality}
                              </span>
                            </td>
                            <td className="text-center px-2 py-2.5 text-zinc-400">
                              {file.language}
                            </td>
                            <td className="text-right px-2 py-2.5 text-zinc-400 tabular-nums">
                              {formatSize(file.size)}
                            </td>
                            <td className="text-right px-2 py-2.5 text-zinc-500 text-xs">
                              {formatDate(file.modified_at)}
                            </td>
                            <td className="px-4 py-2.5 text-right">
                              <button
                                onClick={() => handleDelete(file, group)}
                                disabled={deleting === file.id}
                                className="text-red-500 hover:text-red-400 disabled:text-zinc-700 transition-colors"
                                title="Smazat soubor"
                              >
                                {deleting === file.id ? (
                                  spinnerSvg
                                ) : (
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                    />
                                  </svg>
                                )}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <DownloadPanel />
    </main>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import {
  LibraryMovie,
  LibraryShow,
  LibraryShowDetail,
  TMDBSearchResult,
  scanLibrary,
  getLibraryMovies,
  getLibraryShows,
  getShowDetail,
  searchTMDBForFix,
  fixMovieMatch,
  formatSize,
} from "@/lib/api";
import DownloadPanel from "@/components/DownloadPanel";

type Tab = "filmy" | "serialy";

const QUALITY_COLORS: Record<string, string> = {
  "2160p": "bg-amber-900/60 text-amber-300",
  "1080p": "bg-green-900/60 text-green-300",
  "720p": "bg-blue-900/60 text-blue-300",
  "480p": "bg-zinc-700 text-zinc-300",
  unknown: "bg-zinc-800 text-zinc-500",
};

export default function LibraryPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("filmy");
  const [movies, setMovies] = useState<LibraryMovie[]>([]);
  const [shows, setShows] = useState<LibraryShow[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [selectedShow, setSelectedShow] = useState<LibraryShowDetail | null>(null);
  const [showLoading, setShowLoading] = useState(false);
  const [fixingMovie, setFixingMovie] = useState<LibraryMovie | null>(null);
  const [fixQuery, setFixQuery] = useState("");
  const [fixResults, setFixResults] = useState<TMDBSearchResult[]>([]);
  const [fixSearching, setFixSearching] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [m, s] = await Promise.all([getLibraryMovies(), getLibraryShows()]);
      setMovies(m);
      setShows(s);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleScan() {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await scanLibrary();
      setScanResult(
        `Nalezeno ${result.movies_matched} filmu a ${result.shows_found} serialu (${result.episodes_matched} epizod)`
      );
      await loadData();
    } catch (e) {
      setScanResult("Chyba pri skenovani");
    } finally {
      setScanning(false);
    }
  }

  async function handleShowClick(show: LibraryShow) {
    setShowLoading(true);
    try {
      const detail = await getShowDetail(show.tmdb_id);
      setSelectedShow(detail);
    } catch {
      // ignore
    } finally {
      setShowLoading(false);
    }
  }

  function handleSearchEpisode(showTitle: string, season: number, episode: number) {
    const query = `${showTitle} S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
    router.push(`/?q=${encodeURIComponent(query)}`);
  }

  return (
    <main className="flex flex-col gap-8 px-4 py-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-zinc-500 hover:text-zinc-300 transition-colors text-sm">
            &larr; Hledat
          </Link>
          <h1 className="text-2xl font-bold text-zinc-100">Knihovna</h1>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 text-white text-sm font-medium transition-colors"
        >
          {scanning ? "Skenuji..." : "Skenovat"}
        </button>
      </div>

      {scanResult && (
        <div className="rounded-lg bg-violet-900/20 border border-violet-800 px-4 py-3 text-violet-300 text-sm">
          {scanResult}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-900 rounded-lg p-1 w-fit border border-zinc-800">
        <button
          onClick={() => { setTab("filmy"); setSelectedShow(null); }}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
            tab === "filmy" ? "bg-violet-600 text-white shadow" : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Filmy ({movies.length})
        </button>
        <button
          onClick={() => { setTab("serialy"); setSelectedShow(null); }}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
            tab === "serialy" ? "bg-violet-600 text-white shadow" : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          Serialy ({shows.length})
        </button>
      </div>

      {loading ? (
        <div className="text-zinc-500 animate-pulse text-center py-12">Nacitam...</div>
      ) : tab === "filmy" ? (
        /* ═══ MOVIES TAB ═══ */
        movies.length === 0 ? (
          <div className="text-center py-12 text-zinc-500">
            Zadne filmy. Klikni &quot;Skenovat&quot; pro nacteni knihovny.
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-3">
            {movies.map((movie) => (
              <div
                key={movie.id}
                className="group rounded-lg overflow-hidden bg-zinc-900 border border-zinc-800 hover:border-violet-500 transition-colors"
              >
                <div className="aspect-[2/3] relative bg-zinc-800">
                  {movie.poster_url ? (
                    <Image
                      src={movie.poster_url}
                      alt={movie.title}
                      fill
                      sizes="(max-width: 640px) 33vw, 12.5vw"
                      className="object-cover"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-zinc-600 text-xs">
                      Bez plakatu
                    </div>
                  )}
                  {movie.quality && movie.quality !== "unknown" && (
                    <span className={`absolute top-1 right-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${QUALITY_COLORS[movie.quality] || QUALITY_COLORS.unknown}`}>
                      {movie.quality}
                    </span>
                  )}
                  {movie.matched_by === "filename" && (
                    <span className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-orange-900/80 text-orange-300 text-[9px] font-bold">
                      ?
                    </span>
                  )}
                </div>
                <div className="p-2">
                  <p className="text-sm font-medium text-zinc-100 truncate">{movie.title}</p>
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    {movie.year && <span>{movie.year}</span>}
                    <span>{formatSize(movie.file_size)}</span>
                  </div>
                  {movie.matched_by === "filename" && (
                    <button
                      onClick={() => { setFixingMovie(movie); setFixQuery(movie.filename.replace(/\.[^.]+$/, "")); setFixResults([]); }}
                      className="mt-1 text-[10px] text-orange-400 hover:text-orange-300 transition-colors"
                    >
                      Opravit match
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )
      ) : selectedShow ? (
        /* ═══ SHOW DETAIL ═══ */
        <div className="space-y-4">
          <button
            onClick={() => setSelectedShow(null)}
            className="text-zinc-500 hover:text-zinc-300 transition-colors text-sm"
          >
            &larr; Zpet na serialy
          </button>

          <div className="flex gap-6">
            {selectedShow.poster_url && (
              <div className="w-32 flex-shrink-0">
                <Image
                  src={selectedShow.poster_url}
                  alt={selectedShow.title}
                  width={128}
                  height={192}
                  className="rounded-lg"
                />
              </div>
            )}
            <div>
              <h2 className="text-xl font-bold text-zinc-100">
                {selectedShow.title}
                {selectedShow.year && <span className="text-zinc-500 font-normal ml-2">({selectedShow.year})</span>}
              </h2>
              <p className="text-sm text-zinc-400 mt-1 line-clamp-3">{selectedShow.overview}</p>
              <p className="text-xs text-zinc-500 mt-2">
                {selectedShow.total_seasons} sezon · {selectedShow.total_episodes} epizod celkem
              </p>
            </div>
          </div>

          {/* Seasons accordion */}
          {selectedShow.seasons.map((season) => {
            const owned = season.episodes.filter((e) => e.has_file).length;
            const total = season.episodes.length;
            return (
              <details key={season.season_number} className="group border border-zinc-800 rounded-lg">
                <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-zinc-900/50">
                  <div className="flex items-center gap-3">
                    <span className="text-zinc-100 font-medium">Sezona {season.season_number}</span>
                    <span className="text-xs text-zinc-500">{owned}/{total} epizod</span>
                  </div>
                  <div className="w-24 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-violet-600 rounded-full transition-all"
                      style={{ width: `${total > 0 ? (owned / total) * 100 : 0}%` }}
                    />
                  </div>
                </summary>
                <div className="border-t border-zinc-800">
                  {season.episodes.map((ep) => (
                    <div
                      key={ep.episode}
                      className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800/50 last:border-0"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <span className={`w-5 h-5 flex items-center justify-center rounded-full text-xs ${
                          ep.has_file ? "bg-green-900/60 text-green-400" : "bg-zinc-800 text-zinc-600"
                        }`}>
                          {ep.has_file ? "✓" : ep.episode}
                        </span>
                        <div className="min-w-0 flex-1">
                          <span className="text-sm text-zinc-200">
                            E{String(ep.episode).padStart(2, "0")}
                            {ep.title && <span className="text-zinc-400 ml-2">{ep.title}</span>}
                          </span>
                          {ep.has_file && (
                            <span className="text-xs text-zinc-600 ml-2">
                              {ep.quality && <span className="mr-1">{ep.quality}</span>}
                              {formatSize(ep.file_size)}
                            </span>
                          )}
                        </div>
                      </div>
                      {!ep.has_file && (
                        <button
                          onClick={() => handleSearchEpisode(selectedShow.title, season.season_number, ep.episode)}
                          className="px-3 py-1 rounded bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium transition-colors flex-shrink-0"
                        >
                          Hledat
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            );
          })}
        </div>
      ) : (
        /* ═══ SHOWS GRID ═══ */
        shows.length === 0 ? (
          <div className="text-center py-12 text-zinc-500">
            Zadne serialy. Klikni &quot;Skenovat&quot; pro nacteni knihovny.
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-3">
            {shows.map((show) => {
              const progress = show.total_episodes > 0
                ? Math.round((show.owned_episodes / show.total_episodes) * 100)
                : 0;
              return (
                <button
                  key={show.tmdb_id}
                  onClick={() => handleShowClick(show)}
                  className="group rounded-lg overflow-hidden bg-zinc-900 border border-zinc-800 hover:border-violet-500 transition-colors text-left"
                >
                  <div className="aspect-[2/3] relative bg-zinc-800">
                    {show.poster_url ? (
                      <Image
                        src={show.poster_url}
                        alt={show.title}
                        fill
                        sizes="(max-width: 640px) 33vw, 12.5vw"
                        className="object-cover group-hover:opacity-80 transition-opacity"
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full text-zinc-600 text-xs">
                        Bez plakatu
                      </div>
                    )}
                  </div>
                  <div className="p-2">
                    <p className="text-sm font-medium text-zinc-100 truncate">{show.title}</p>
                    <div className="flex items-center gap-2 text-xs text-zinc-500 mt-0.5">
                      {show.year && <span>{show.year}</span>}
                      <span>{show.owned_episodes}/{show.total_episodes}</span>
                    </div>
                    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden mt-1.5">
                      <div
                        className="h-full bg-violet-600 rounded-full"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )
      )}

      {showLoading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="text-zinc-300 animate-pulse">Nacitam serial...</div>
        </div>
      )}

      {/* Fix Match Modal */}
      {fixingMovie && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setFixingMovie(null)}>
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-zinc-100">Opravit match</h3>
            <p className="text-sm text-zinc-400 truncate">Soubor: {fixingMovie.filename}</p>
            <p className="text-sm text-zinc-500">Aktualne: <span className="text-zinc-300">{fixingMovie.title} ({fixingMovie.year})</span></p>

            <div className="flex gap-2">
              <input
                type="text"
                value={fixQuery}
                onChange={(e) => setFixQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && fixQuery.trim()) {
                    setFixSearching(true);
                    searchTMDBForFix(fixingMovie.id, fixQuery).then(setFixResults).finally(() => setFixSearching(false));
                  }
                }}
                placeholder="Hledej na TMDB..."
                className="flex-1 rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 focus:border-violet-500 outline-none"
              />
              <button
                onClick={() => {
                  setFixSearching(true);
                  searchTMDBForFix(fixingMovie.id, fixQuery).then(setFixResults).finally(() => setFixSearching(false));
                }}
                disabled={fixSearching}
                className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-500 disabled:opacity-50"
              >
                {fixSearching ? "..." : "Hledat"}
              </button>
            </div>

            {fixResults.length > 0 && (
              <div className="max-h-64 overflow-y-auto space-y-1">
                {fixResults.map((r) => (
                  <button
                    key={r.tmdb_id}
                    onClick={async () => {
                      await fixMovieMatch(fixingMovie.id, r.tmdb_id);
                      setFixingMovie(null);
                      loadData();
                    }}
                    className="flex items-center gap-3 w-full p-2 rounded-lg hover:bg-zinc-800 transition-colors text-left"
                  >
                    {r.poster_url ? (
                      <Image src={r.poster_url} alt="" width={32} height={48} className="rounded" />
                    ) : (
                      <div className="w-8 h-12 bg-zinc-700 rounded" />
                    )}
                    <div>
                      <p className="text-sm text-zinc-100">{r.title}</p>
                      <p className="text-xs text-zinc-500">{r.year} · TMDB {r.tmdb_id}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}

            <button onClick={() => setFixingMovie(null)} className="text-sm text-zinc-500 hover:text-zinc-300">
              Zavrit
            </button>
          </div>
        </div>
      )}

      <DownloadPanel />
    </main>
  );
}

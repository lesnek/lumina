"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import SearchBar from "@/components/SearchBar";
import MovieGrid from "@/components/MovieGrid";
import FileTable from "@/components/FileTable";
import {
  TMDBMovie,
  ScoredFile,
  searchMovies,
  searchFiles,
  getSetupStatus,
} from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [movies, setMovies] = useState<TMDBMovie[]>([]);
  const [files, setFiles] = useState<ScoredFile[]>([]);
  const [selectedMovie, setSelectedMovie] = useState<TMDBMovie | null>(null);
  const [moviesLoading, setMoviesLoading] = useState(false);
  const [filesLoading, setFilesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        if (!status.complete) {
          router.replace("/setup");
        } else {
          setReady(true);
        }
      })
      .catch(() => setReady(true)); // if API is down, show the page anyway
  }, [router]);

  const [searchLang, setSearchLang] = useState<string | undefined>(undefined);

  async function handleSearch(query: string, language?: string) {
    setError(null);
    setMovies([]);
    setFiles([]);
    setSelectedMovie(null);
    setMoviesLoading(true);
    setSearchLang(language);
    try {
      const results = await searchMovies(query, language);
      setMovies(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search error");
    } finally {
      setMoviesLoading(false);
    }
  }

  async function handleSelectMovie(movie: TMDBMovie) {
    setSelectedMovie(movie);
    setFiles([]);
    setFilesLoading(true);
    setError(null);
    try {
      const query = movie.year
        ? `${movie.title} ${movie.year}`
        : movie.title;
      const results = await searchFiles(query, searchLang);
      setFiles(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "File search error");
    } finally {
      setFilesLoading(false);
    }
  }

  if (!ready) {
    return (
      <main className="flex items-center justify-center min-h-[calc(100vh-57px)]">
        <div className="text-zinc-600 text-sm animate-pulse">Nacitam...</div>
      </main>
    );
  }

  return (
    <main className="flex flex-col items-center gap-8 px-4 py-12 max-w-7xl mx-auto">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
          Lumina
        </h1>
        <p className="text-zinc-500 text-sm">
          DDL a torrent obsah &mdash; vyhledej, vyber, stáhni
        </p>
      </div>

      <SearchBar onSearch={handleSearch} loading={moviesLoading} />

      {error && (
        <div className="rounded-lg bg-red-900/30 border border-red-800 px-4 py-3 text-red-300 text-sm w-full max-w-2xl">
          {error}
        </div>
      )}

      {!selectedMovie && (
        <MovieGrid movies={movies} onSelect={handleSelectMovie} />
      )}

      {selectedMovie && (
        <div className="w-full space-y-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                setSelectedMovie(null);
                setFiles([]);
              }}
              className="text-zinc-500 hover:text-zinc-300 transition-colors text-sm"
            >
              &larr; Zpět na výsledky
            </button>
            <h2 className="text-xl font-semibold text-zinc-100">
              {selectedMovie.title}
              {selectedMovie.year && (
                <span className="text-zinc-500 font-normal ml-2">
                  ({selectedMovie.year})
                </span>
              )}
            </h2>
          </div>
          <FileTable files={files} loading={filesLoading} />
        </div>
      )}
    </main>
  );
}

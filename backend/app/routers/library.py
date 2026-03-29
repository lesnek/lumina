"""Library router — scan local media folders, match with TMDB, track episodes."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter

from app.config import get_effective_settings
from app.clients.tmdb import TMDBClient
from app.db import get_db
from app.utils.tv_parser import (
    parse_tv_filename,
    parse_movie_filename,
    normalize_for_search,
    VIDEO_EXTS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/library", tags=["library"])

# Reuse quality/language detection from duplicates
_QUALITY_RE = {
    "2160p": r"2160p|4[Kk]|UHD",
    "1080p": r"1080[pi]|FHD|Full\s*HD",
    "720p": r"720[pi]|HD(?!R)",
    "480p": r"480[pi]|SD",
}

_LANG_RE = {
    "CZ": r"(?i)\b(CZ|[Čč]esk|czech|dabing|dab)\b",
    "SK": r"(?i)\b(SK|[Ss]lovensk|slovak)\b",
    "EN": r"(?i)\b(EN|ENG|english)\b",
    "JP": r"(?i)\b(JP|JPN|japanese)\b",
}


def _detect_quality(name: str) -> str:
    import re
    for label, pattern in _QUALITY_RE.items():
        if re.search(pattern, name):
            return label
    return "unknown"


def _detect_language(name: str) -> str:
    import re
    langs = []
    for code, pattern in _LANG_RE.items():
        if re.search(pattern, name):
            langs.append(code)
    return ",".join(langs) if langs else ""


def _scan_video_files(directory: str) -> list[dict]:
    """Walk directory and return list of video files with metadata."""
    files = []
    if not os.path.isdir(directory):
        return files
    for root, _dirs, filenames in os.walk(directory):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in VIDEO_EXTS:
                continue
            full_path = os.path.join(root, fname)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            files.append({
                "filename": fname,
                "file_path": full_path,
                "file_size": stat.st_size,
                "added_at": stat.st_mtime,
                "quality": _detect_quality(fname),
                "language": _detect_language(fname),
            })
    return files


# ─── SCAN ───

@router.post("/scan")
async def scan_library():
    """Scan movie + TV directories, match with TMDB, store in DB."""
    cfg = await get_effective_settings()
    movie_dir = cfg.get("plex_media_dir", "")
    tv_dir = cfg.get("tv_media_dir", "")
    tmdb_key = cfg.get("tmdb_api_key", "")

    if not tmdb_key:
        return {"error": "TMDB API key not configured"}

    client = TMDBClient(tmdb_key)
    db = await get_db()
    stats = {"movies_found": 0, "movies_matched": 0, "shows_found": 0, "episodes_matched": 0}

    try:
        # --- Cleanup: remove DB entries where file no longer exists ---
        cursor = await db.execute("SELECT id, file_path FROM library_movies")
        for row in await cursor.fetchall():
            if not os.path.exists(row[1]):
                await db.execute("DELETE FROM library_movies WHERE id = ?", (row[0],))
        cursor = await db.execute("SELECT id, file_path FROM library_episodes WHERE has_file = 1")
        for row in await cursor.fetchall():
            if not os.path.exists(row[1]):
                await db.execute("UPDATE library_episodes SET has_file = 0, file_path = NULL, filename = NULL WHERE id = ?", (row[0],))
        # Remove shows with zero episodes
        await db.execute("DELETE FROM library_shows WHERE tmdb_id NOT IN (SELECT DISTINCT show_tmdb_id FROM library_episodes WHERE has_file = 1)")
        await db.commit()

        # --- Scan movies ---
        if movie_dir:
            movie_files = _scan_video_files(movie_dir)
            stats["movies_found"] = len(movie_files)

            for f in movie_files:
                # Skip if already in DB
                cursor = await db.execute(
                    "SELECT id FROM library_movies WHERE file_path = ?",
                    (f["file_path"],),
                )
                if await cursor.fetchone():
                    stats["movies_matched"] += 1
                    continue

                parsed = parse_movie_filename(f["filename"])
                if not parsed:
                    continue

                # Search TMDB — try multiple queries
                title = parsed["title"]
                year = parsed.get("year")
                queries = []
                if year:
                    queries.append(f"{title} {year}")
                queries.append(title)
                # Also try without diacritics
                stripped = normalize_for_search(title)
                if stripped != title.lower():
                    if year:
                        queries.append(f"{stripped} {year}")
                    queries.append(stripped)

                try:
                    results = None
                    for search_q in queries:
                        results = await client.search_movie(search_q)
                        if results:
                            break
                    if results:
                        movie = results[0]
                        await db.execute(
                            """INSERT OR REPLACE INTO library_movies
                            (tmdb_id, title, original_title, year, poster_url, overview,
                             filename, file_path, file_size, quality, language, added_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime(?, 'unixepoch'))""",
                            (movie.tmdb_id, movie.title, movie.original_title, movie.year,
                             movie.poster_url, movie.overview,
                             f["filename"], f["file_path"], f["file_size"],
                             f["quality"], f["language"], f["added_at"]),
                        )
                        stats["movies_matched"] += 1
                except Exception as e:
                    logger.warning("TMDB match failed for '%s': %s", f["filename"], e)

            await db.commit()

        # --- Scan TV shows ---
        if tv_dir:
            tv_files = _scan_video_files(tv_dir)

            # Group by show name
            show_groups: dict[str, list[dict]] = {}
            for f in tv_files:
                parsed = parse_tv_filename(f["filename"], f["file_path"])
                if not parsed:
                    continue
                key = normalize_for_search(parsed["show_name"])
                if key not in show_groups:
                    show_groups[key] = []
                show_groups[key].append({**f, **parsed})

            stats["shows_found"] = len(show_groups)

            for show_key, episodes in show_groups.items():
                # Use first episode's show_name for TMDB search
                show_name = episodes[0]["show_name"]
                year = episodes[0].get("year")

                # Check if already in DB by searching existing shows
                cursor = await db.execute(
                    "SELECT tmdb_id FROM library_shows WHERE lower(title) = lower(?) OR lower(original_title) = lower(?)",
                    (show_name, show_name),
                )
                existing = await cursor.fetchone()

                if existing:
                    tmdb_id = existing[0]
                else:
                    # Search TMDB for the show
                    search_q = f"{show_name} {year}" if year else show_name
                    try:
                        results = await client.search_tv(search_q)
                        if not results:
                            logger.warning("No TMDB match for show '%s'", show_name)
                            continue
                        tmdb_id = results[0].tmdb_id

                        # Get full details
                        details = await client.get_tv_details(tmdb_id)
                        await db.execute(
                            """INSERT OR REPLACE INTO library_shows
                            (tmdb_id, title, original_title, year, poster_url, overview,
                             total_seasons, total_episodes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (tmdb_id, details["title"], details["original_title"],
                             details["first_air_date"][:4] if details.get("first_air_date") else "",
                             details["poster_url"], details["overview"],
                             details["total_seasons"], details["total_episodes"]),
                        )

                        # Populate all episodes from TMDB
                        for season_info in details["seasons"]:
                            sn = season_info["season_number"]
                            try:
                                tmdb_episodes = await client.get_season(tmdb_id, sn)
                                for ep in tmdb_episodes:
                                    await db.execute(
                                        """INSERT OR IGNORE INTO library_episodes
                                        (show_tmdb_id, season, episode, episode_title, air_date)
                                        VALUES (?, ?, ?, ?, ?)""",
                                        (tmdb_id, sn, ep["episode_number"],
                                         ep["name"], ep["air_date"]),
                                    )
                            except Exception as e:
                                logger.warning("Failed to fetch S%02d for %s: %s", sn, show_name, e)

                    except Exception as e:
                        logger.warning("TMDB match failed for show '%s': %s", show_name, e)
                        continue

                # Mark episodes we have on disk
                for ep_data in episodes:
                    await db.execute(
                        """UPDATE library_episodes
                        SET has_file = 1, filename = ?, file_path = ?,
                            file_size = ?, quality = ?, language = ?
                        WHERE show_tmdb_id = ? AND season = ? AND episode = ?""",
                        (ep_data["filename"], ep_data["file_path"],
                         ep_data["file_size"], ep_data["quality"], ep_data["language"],
                         tmdb_id, ep_data["season"], ep_data["episode"]),
                    )
                    stats["episodes_matched"] += 1

            await db.commit()

    finally:
        await client.close()
        await db.close()

    logger.info("Library scan complete: %s", stats)
    return stats


# ─── MOVIES ───

@router.get("/movies")
async def get_library_movies():
    """List all movies in library."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, tmdb_id, title, original_title, year, poster_url,
                      filename, file_size, quality, language, added_at
            FROM library_movies ORDER BY added_at DESC"""
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "tmdb_id": r[1], "title": r[2],
                "original_title": r[3], "year": r[4], "poster_url": r[5],
                "filename": r[6], "file_size": r[7], "quality": r[8],
                "language": r[9], "added_at": r[10],
            }
            for r in rows
        ]
    finally:
        await db.close()


@router.delete("/movies/{movie_id}")
async def delete_library_movie(movie_id: int):
    """Remove movie from library DB (not from disk)."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM library_movies WHERE id = ?", (movie_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


# ─── SHOWS ───

@router.get("/shows")
async def get_library_shows():
    """List all TV shows with episode count progress."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT s.tmdb_id, s.title, s.original_title, s.year, s.poster_url,
                      s.total_seasons, s.total_episodes,
                      COUNT(CASE WHEN e.has_file = 1 THEN 1 END) as owned_episodes
            FROM library_shows s
            LEFT JOIN library_episodes e ON e.show_tmdb_id = s.tmdb_id
            GROUP BY s.tmdb_id
            ORDER BY s.title"""
        )
        rows = await cursor.fetchall()
        return [
            {
                "tmdb_id": r[0], "title": r[1], "original_title": r[2],
                "year": r[3], "poster_url": r[4],
                "total_seasons": r[5], "total_episodes": r[6],
                "owned_episodes": r[7],
            }
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/shows/{tmdb_id}")
async def get_show_detail(tmdb_id: int):
    """Get show detail with all seasons and episodes (owned/missing)."""
    db = await get_db()
    try:
        # Show info
        cursor = await db.execute(
            "SELECT tmdb_id, title, original_title, year, poster_url, overview, total_seasons, total_episodes FROM library_shows WHERE tmdb_id = ?",
            (tmdb_id,),
        )
        show = await cursor.fetchone()
        if not show:
            return {"error": "Show not found"}

        # Episodes
        cursor = await db.execute(
            """SELECT season, episode, episode_title, air_date,
                      has_file, filename, file_size, quality, language
            FROM library_episodes
            WHERE show_tmdb_id = ?
            ORDER BY season, episode""",
            (tmdb_id,),
        )
        rows = await cursor.fetchall()

        # Group by season
        seasons: dict[int, list] = {}
        for r in rows:
            sn = r[0]
            if sn not in seasons:
                seasons[sn] = []
            seasons[sn].append({
                "episode": r[1], "title": r[2], "air_date": r[3],
                "has_file": bool(r[4]), "filename": r[5] or "",
                "file_size": r[6] or 0, "quality": r[7] or "",
                "language": r[8] or "",
            })

        return {
            "tmdb_id": show[0], "title": show[1], "original_title": show[2],
            "year": show[3], "poster_url": show[4], "overview": show[5],
            "total_seasons": show[6], "total_episodes": show[7],
            "seasons": [
                {"season_number": sn, "episodes": eps}
                for sn, eps in sorted(seasons.items())
            ],
        }
    finally:
        await db.close()


@router.delete("/shows/{tmdb_id}")
async def delete_library_show(tmdb_id: int):
    """Remove show and its episodes from library DB."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM library_episodes WHERE show_tmdb_id = ?", (tmdb_id,))
        await db.execute("DELETE FROM library_shows WHERE tmdb_id = ?", (tmdb_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()

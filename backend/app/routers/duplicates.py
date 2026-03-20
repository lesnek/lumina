import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import get_effective_settings
from app.db import DB_PATH, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])

# Known video extensions
VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".wmv", ".flv", ".mov", ".m4v",
    ".ts", ".webm", ".mpg", ".mpeg", ".divx", ".ogm",
}

# Patterns to strip from filenames for grouping
_STRIP_PATTERNS = [
    # Release group tags
    r"\[.*?\]",
    # Quality/codec tags
    r"(?i)\b(BluRay|BDRip|BRRip|WEBRip|WEB-DL|WEBDL|WEB|HDRip|DVDRip|HDTV|"
    r"PDTV|DVDScr|TS|CAM|R5|HC|REMUX|Blu-Ray)\b",
    r"(?i)\b(x264|x265|h264|h\.264|h265|h\.265|HEVC|AVC|XviD|DivX|AAC|AC3|"
    r"DTS|FLAC|MP3|DD5\.1|DD2\.0|Atmos|TrueHD|10bit)\b",
    # Resolution
    r"(?i)\b(2160p|1080p|720p|480p|4K|UHD|FHD|HD)\b",
    # Language/dub tags
    r"(?i)\b(CZ|SK|EN|ENG|DABING|dab|dabing|titulky|sub|subs|dubbed|dual|multi)\b",
    # Common noise
    r"(?i)\b(RARBG|YTS|YIFY|GalaxyRG|FGT|EVO|SPARKS|GECKOS|NTb|PSA|ION10)\b",
    r"[-._]",
]

# Year pattern
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _normalize_title(filename: str) -> tuple[str, str]:
    """Extract normalized title and year from a video filename.

    Returns (normalized_title, year) where year may be empty string.
    """
    # Remove extension
    name = Path(filename).stem

    # Extract year
    year_match = _YEAR_RE.search(name)
    year = year_match.group(1) if year_match else ""

    # Strip everything after year (usually quality/codec info)
    if year_match:
        name = name[: year_match.start()]

    # Apply strip patterns
    for pattern in _STRIP_PATTERNS:
        name = re.sub(pattern, " ", name)

    # Normalize whitespace and case
    name = re.sub(r"\s+", " ", name).strip().lower()

    return name, year


def _detect_quality(filename: str) -> str:
    """Detect video quality from filename."""
    fn = filename.upper()
    if "2160P" in fn or "4K" in fn or "UHD" in fn:
        return "2160p"
    if "1080P" in fn or "FHD" in fn:
        return "1080p"
    if "720P" in fn or "HD" in fn:
        return "720p"
    if "480P" in fn or "SD" in fn:
        return "480p"
    return "unknown"


def _detect_language(filename: str) -> str:
    """Detect language/dub from filename."""
    fn = filename.upper()
    tags = []
    if "CZ" in fn or "DABING" in fn or "DAB" in fn:
        tags.append("CZ")
    if re.search(r"\bSK\b", fn):
        tags.append("SK")
    if re.search(r"\bEN\b", fn) or re.search(r"\bENG\b", fn):
        tags.append("EN")
    return "/".join(tags) if tags else "-"


async def _ensure_table() -> None:
    """Create duplicates table if not exists."""
    db = await get_db()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS scanned_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                year TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                quality TEXT NOT NULL DEFAULT 'unknown',
                language TEXT NOT NULL DEFAULT '-',
                modified_at TEXT NOT NULL DEFAULT '',
                scanned_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_scanned_norm_title "
            "ON scanned_files (normalized_title, year)"
        )
        await db.commit()
    finally:
        await db.close()


@router.post("/scan")
async def scan_for_duplicates() -> dict:
    """Scan plex_media_dir for video files and detect duplicates."""
    cfg = await get_effective_settings()
    media_dir = cfg["plex_media_dir"]

    if not os.path.isdir(media_dir):
        raise HTTPException(400, f"Media directory not found: {media_dir}")

    await _ensure_table()

    # Walk the directory tree
    found_files: list[dict] = []
    for root, _dirs, files in os.walk(media_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in VIDEO_EXTS:
                continue

            full_path = os.path.join(root, fname)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue

            norm_title, year = _normalize_title(fname)
            if not norm_title:
                continue

            found_files.append({
                "path": full_path,
                "filename": fname,
                "normalized_title": norm_title,
                "year": year,
                "size": stat.st_size,
                "quality": _detect_quality(fname),
                "language": _detect_language(fname),
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })

    # Upsert into DB
    db = await get_db()
    try:
        # Clear old entries that no longer exist on disk
        await db.execute("DELETE FROM scanned_files")

        for f in found_files:
            await db.execute(
                """
                INSERT INTO scanned_files
                    (path, filename, normalized_title, year, size, quality, language, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f["path"], f["filename"], f["normalized_title"],
                    f["year"], f["size"], f["quality"], f["language"],
                    f["modified_at"],
                ),
            )
        await db.commit()
    finally:
        await db.close()

    logger.info("Scanned %d video files in %s", len(found_files), media_dir)
    return {"scanned": len(found_files), "media_dir": media_dir}


@router.get("")
async def get_duplicates() -> dict:
    """Return groups of duplicate files (same normalized title + year)."""
    await _ensure_table()

    db = await get_db()
    try:
        # Find groups with more than 1 file
        cursor = await db.execute(
            """
            SELECT normalized_title, year, COUNT(*) as cnt
            FROM scanned_files
            GROUP BY normalized_title, year
            HAVING cnt > 1
            ORDER BY cnt DESC, normalized_title
            """
        )
        groups_raw = await cursor.fetchall()

        groups = []
        for g in groups_raw:
            title = g["normalized_title"]
            year = g["year"]

            cursor2 = await db.execute(
                """
                SELECT id, path, filename, size, quality, language, modified_at
                FROM scanned_files
                WHERE normalized_title = ? AND year = ?
                ORDER BY size DESC
                """,
                (title, year),
            )
            files = [dict(row) for row in await cursor2.fetchall()]

            # Nice display title: capitalize first letters
            display_title = title.title()
            if year:
                display_title += f" ({year})"

            groups.append({
                "title": display_title,
                "normalized_title": title,
                "year": year,
                "count": len(files),
                "files": files,
            })

        return {"groups": groups, "total_groups": len(groups)}
    finally:
        await db.close()


@router.delete("/file/{file_id}")
async def delete_file(file_id: int) -> dict:
    """Delete a specific file from disk and remove from DB."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT path, filename FROM scanned_files WHERE id = ?", (file_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "File not found in scan database")

        file_path = row["path"]

        # Delete from disk
        try:
            os.remove(file_path)
            logger.info("Deleted file: %s", file_path)
        except FileNotFoundError:
            logger.warning("File already gone: %s", file_path)
        except OSError as e:
            raise HTTPException(500, f"Failed to delete file: {e}")

        # Remove from DB
        await db.execute("DELETE FROM scanned_files WHERE id = ?", (file_id,))
        await db.commit()

        return {"ok": True, "deleted": row["filename"]}
    finally:
        await db.close()

import json
import logging
import os
from pathlib import Path

import aiosqlite

logger = logging.getLogger("app.db")

DB_PATH = Path("data/lumina.db")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db() -> None:
    """Create tables and optionally migrate legacy .env credentials."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await get_db()
    try:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                config TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS automations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                config TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS download_tracker (
                id TEXT PRIMARY KEY,
                tmdb_id INTEGER,
                title TEXT,
                year INTEGER,
                backend TEXT,
                status TEXT,
                target_dir TEXT,
                content_type TEXT DEFAULT 'movie',
                processed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS library_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tmdb_id INTEGER,
                title TEXT,
                original_title TEXT,
                year TEXT,
                poster_url TEXT,
                overview TEXT,
                filename TEXT,
                file_path TEXT UNIQUE,
                file_size INTEGER DEFAULT 0,
                quality TEXT DEFAULT '',
                language TEXT DEFAULT '',
                added_at TEXT,
                scanned_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS library_shows (
                tmdb_id INTEGER PRIMARY KEY,
                title TEXT,
                original_title TEXT,
                year TEXT,
                poster_url TEXT,
                overview TEXT,
                total_seasons INTEGER DEFAULT 0,
                total_episodes INTEGER DEFAULT 0,
                scanned_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS library_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_tmdb_id INTEGER REFERENCES library_shows(tmdb_id) ON DELETE CASCADE,
                season INTEGER,
                episode INTEGER,
                episode_title TEXT DEFAULT '',
                air_date TEXT DEFAULT '',
                filename TEXT DEFAULT '',
                file_path TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                quality TEXT DEFAULT '',
                language TEXT DEFAULT '',
                has_file INTEGER DEFAULT 0,
                UNIQUE(show_tmdb_id, season, episode)
            );
            """
        )
        await db.execute("INSERT OR IGNORE INTO automations (type, name, enabled) VALUES ('radarr', 'Radarr', 0)")
        await db.execute("INSERT OR IGNORE INTO automations (type, name, enabled) VALUES ('sonarr', 'Sonarr', 0)")
        await db.execute("INSERT OR IGNORE INTO automations (type, name, enabled) VALUES ('renamer', 'Renamer (Media Info)', 0)")

        # Migrations for existing DBs
        try:
            await db.execute("ALTER TABLE download_tracker ADD COLUMN content_type TEXT DEFAULT 'movie'")
        except Exception:
            pass  # column already exists

        await db.commit()

        # Auto-migrate from .env if tables are empty
        cursor = await db.execute("SELECT COUNT(*) FROM sources")
        row = await cursor.fetchone()
        if row and row[0] == 0:
            await _migrate_sources_from_env(db)

        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        row = await cursor.fetchone()
        if row and row[0] == 0:
            await _migrate_settings_from_env(db)
    finally:
        await db.close()


async def _migrate_sources_from_env(db: aiosqlite.Connection) -> None:
    """Seed sources table from legacy .env settings (one-time migration)."""
    migrated = 0

    ws_user = os.getenv("WEBSHARE_USERNAME", "")
    ws_pass = os.getenv("WEBSHARE_PASSWORD", "")
    if ws_user and ws_pass:
        config = json.dumps({"username": ws_user, "password": ws_pass})
        await db.execute(
            "INSERT INTO sources (type, name, config) VALUES (?, ?, ?)",
            ("webshare", "WebShare", config),
        )
        migrated += 1

    fs_user = os.getenv("FASTSHARE_USERNAME", "")
    fs_pass = os.getenv("FASTSHARE_PASSWORD", "")
    if fs_user and fs_pass:
        config = json.dumps({"login": fs_user, "password": fs_pass})
        await db.execute(
            "INSERT INTO sources (type, name, config) VALUES (?, ?, ?)",
            ("fastshare", "FastShare", config),
        )
        migrated += 1

    jk_url = os.getenv("JACKETT_URL", "")
    jk_key = os.getenv("JACKETT_API_KEY", "")
    if jk_url and jk_key:
        config = json.dumps({"url": jk_url, "api_key": jk_key})
        await db.execute(
            "INSERT INTO sources (type, name, config) VALUES (?, ?, ?)",
            ("jackett", "Jackett", config),
        )
        migrated += 1

    if migrated:
        await db.commit()
        logger.info("Migrated %d source(s) from .env to database", migrated)


# Mapping from settings DB key to .env variable name
_ENV_MIGRATION_MAP = {
    "tmdb_api_key": "TMDB_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "aria2_rpc_url": "ARIA2_RPC_URL",
    "aria2_rpc_secret": "ARIA2_RPC_SECRET",
    "plex_media_dir": "PLEX_MEDIA_DIR",
    "qbittorrent_url": "QBITTORRENT_URL",
    "qbittorrent_username": "QBITTORRENT_USERNAME",
    "qbittorrent_password": "QBITTORRENT_PASSWORD",
}


async def _migrate_settings_from_env(db: aiosqlite.Connection) -> None:
    """Seed settings table from .env variables (one-time migration)."""
    migrated = 0
    for db_key, env_var in _ENV_MIGRATION_MAP.items():
        value = os.getenv(env_var, "")
        if value:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (db_key, value),
            )
            migrated += 1

    if migrated:
        await db.commit()
        logger.info("Migrated %d setting(s) from .env to database", migrated)


async def get_setting(key: str, default: str = "") -> str:
    """Read a single setting from DB, with fallback to default."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default
    finally:
        await db.close()


async def get_all_settings() -> dict[str, str]:
    """Read all settings from DB."""
    db = await get_db()
    try:
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}
    finally:
        await db.close()


async def set_settings(updates: dict[str, str]) -> None:
    """Upsert multiple settings at once."""
    db = await get_db()
    try:
        for key, value in updates.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await db.commit()
    finally:
        await db.close()

# --- Automation & Tracking helpers ---

async def get_automations():
    """Fetch all configured automations."""
    db = await get_db()
    try:
        async with db.execute("SELECT id, type, name, enabled, config FROM automations") as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0], "type": r[1], "name": r[2],
                    "enabled": bool(r[3]), "config": json.loads(r[4])
                }
                for r in rows
            ]
    finally:
        await db.close()

async def update_automation(type_name: str, enabled: bool = None, config: dict = None):
    """Update automation status or configuration."""
    db = await get_db()
    try:
        if enabled is not None:
            await db.execute("UPDATE automations SET enabled = ? WHERE type = ?", (1 if enabled else 0, type_name))
        if config is not None:
            await db.execute("UPDATE automations SET config = ? WHERE type = ?", (json.dumps(config), type_name))
        await db.commit()
    finally:
        await db.close()

async def track_download(id: str, tmdb_id: int, title: str, year: int, backend: str, target_dir: str, content_type: str = "movie"):
    """Record a new download for background monitoring."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO download_tracker (id, tmdb_id, title, year, backend, status, target_dir, content_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (id, tmdb_id, title, year, backend, "active", target_dir, content_type)
        )
        await db.commit()
    finally:
        await db.close()

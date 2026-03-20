import json
import logging
import os
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

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
            """
        )
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
        cursor = await db.execute("SELECT key, value FROM settings")
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

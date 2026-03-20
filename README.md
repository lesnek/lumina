# Lumina

Lightweight orchestrator for downloading content from DDL storage and torrent sources to a Plex server.
Built as a simpler alternative to the Radarr/Sonarr stack, with AI-powered file scoring, multi-language dubbing detection, and manual quality approval before download.

![Stack](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Stack](https://img.shields.io/badge/Next.js_14-000?logo=nextdotjs&logoColor=white)
![Stack](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![Stack](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Stack](https://img.shields.io/badge/Python_3.11+-3776AB?logo=python&logoColor=white)

## How it works

```
Search movie (TMDB) → Pick title → Lumina searches all sources in parallel
→ AI scores files (quality, dubbing, relevance) → You pick the best one → Download
```

1. **Search** a movie by name via TMDB (localized to your preferred language)
2. **Lumina fans out** to all enabled sources (WebShare, FastShare, Jackett torrent indexers)
3. **AI scoring** via Groq (Llama 3.3 70B) ranks files by quality, dubbing in your language(s), and relevance
4. **You approve** the file you want — no automatic downloads
5. **Download** via Aria2 (direct) or qBittorrent (torrents) into your Plex media folder

## Features

- **Multi-source search** — WebShare.cz, FastShare.cz, torrent indexers via Jackett
- **AI-powered scoring** — Groq Cloud rates each file for quality, dubbing detection, and relevance
- **25 languages** — Pick your preferred languages (CS, SK, EN, DE, PL, FR, ES, ...) for dubbing detection and TMDB metadata
- **Language filter** — Search dropdown to filter results by a specific language
- **Plugin architecture** — Sources are plugins with a common interface, easy to add new ones
- **Setup wizard** — First-run setup guides you through API keys, download config, and source setup
- **Settings UI** — Manage everything from the browser: API keys, download folder, sources, languages, score threshold
- **No `.env` editing** — All configuration stored in SQLite, migrated from `.env` on first run
- **Dark mode UI** — Clean Next.js 14 interface with Tailwind CSS

## Quick start

```bash
git clone https://github.com/your-user/lumina.git
cd lumina
cp .env.example .env
docker compose up -d
```

Open [http://localhost:3000](http://localhost:3000) — the setup wizard will guide you through initial configuration.

### What you'll need

| Service | What for | Where to get |
|---------|----------|-------------|
| **TMDB API Key** | Movie search & metadata | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) |
| **Groq API Key** | AI file scoring (free) | [console.groq.com/keys](https://console.groq.com/keys) |
| **WebShare / FastShare** | DDL source credentials | Your existing account |
| **Jackett** | Torrent indexers (sktorrent, etc.) | Included in Docker Compose |

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐
│  Next.js 14  │────▶│  FastAPI Backend                      │
│  :3000       │     │  :8000                                │
└─────────────┘     │                                      │
                    │  ┌─────────┐  ┌──────────┐           │
                    │  │ Sources │  │ Clients  │           │
                    │  │ Registry│  │          │           │
                    │  │         │  │ • Aria2  │           │
                    │  │ • WS    │  │ • qBit   │           │
                    │  │ • FS    │  │ • TMDB   │           │
                    │  │ • Jackett│ │ • Groq   │           │
                    │  └─────────┘  └──────────┘           │
                    │         │                             │
                    │    ┌────┴────┐                        │
                    │    │ SQLite  │                        │
                    │    │ sources │                        │
                    │    │ settings│                        │
                    │    └─────────┘                        │
                    └──────────────────────────────────────┘
                         │                    │
                    ┌────┴────┐          ┌────┴────┐
                    │  Aria2  │          │ Jackett │
                    │  :6800  │          │  :9117  │
                    └─────────┘          └─────────┘
                         │
                    ┌────┴────┐
                    │/downloads│
                    │  (Plex)  │
                    └──────────┘
```

## Project structure

```
lumina/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, CORS
│   │   ├── config.py            # Settings with DB override
│   │   ├── db.py                # SQLite (sources + settings tables)
│   │   ├── clients/
│   │   │   ├── aria2.py         # Aria2 JSON-RPC
│   │   │   ├── qbittorrent.py   # qBittorrent WebUI API
│   │   │   ├── tmdb.py          # TMDB v3 (multi-language)
│   │   │   ├── groq_scorer.py   # AI scoring (Llama 3.3 70B, 25 langs)
│   │   │   ├── webshare.py      # WebShare.cz XML API
│   │   │   ├── fastshare.py     # FastShare.cz reverse-engineered
│   │   │   └── jackett.py       # Jackett Torznab JSON
│   │   ├── sources/
│   │   │   ├── base.py          # BaseSource ABC, SourceType enum
│   │   │   ├── registry.py      # Singleton SourceRegistry
│   │   │   ├── webshare.py      # WebShare adapter
│   │   │   ├── fastshare.py     # FastShare adapter
│   │   │   └── jackett.py       # Jackett adapter
│   │   ├── routers/
│   │   │   ├── search.py        # /api/search/movies, /api/search/files
│   │   │   ├── download.py      # /api/download
│   │   │   ├── sources.py       # /api/sources CRUD
│   │   │   └── settings.py      # /api/settings + setup-status
│   │   └── models/
│   │       └── schemas.py       # Pydantic models
│   ├── pyproject.toml           # uv / PEP 621
│   ├── uv.lock
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Home — search & results
│   │   │   ├── setup/page.tsx   # First-run wizard
│   │   │   ├── settings/page.tsx # Settings UI
│   │   │   └── layout.tsx       # Nav bar
│   │   ├── components/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── MovieGrid.tsx
│   │   │   └── FileTable.tsx
│   │   └── lib/
│   │       └── api.ts           # API client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Configuration

All settings are managed via the **Settings UI** at [localhost:3000/settings](http://localhost:3000/settings).

On first run, values from `.env` are automatically migrated to the SQLite database. After that, `.env` is only used as a fallback.

| Setting | Default | Description |
|---------|---------|-------------|
| TMDB API Key | — | Movie search metadata |
| Groq API Key | — | AI file scoring |
| Plex Media Dir | `/downloads/plex` | Download target folder |
| Aria2 RPC URL | `http://aria2:6800/jsonrpc` | Aria2 connection |
| Aria2 RPC Secret | — | Aria2 auth token |
| qBittorrent URL | — | qBittorrent WebUI |
| Languages | `cs` | Preferred languages for dubbing detection (comma-separated codes) |
| Min Relevance Score | `70` | Hide files scored below this (0–100) |

## Adding a new source

Sources follow a plugin pattern. To add a new one:

1. Create a client in `backend/app/clients/yoursource.py`
2. Create an adapter in `backend/app/sources/yoursource.py` extending `BaseSource`
3. Add to `SourceType` enum in `base.py`
4. Register in `registry.py` → `_ensure_classes()`

```python
# backend/app/sources/base.py
class BaseSource(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]: ...

    @abstractmethod
    async def get_download_info(self, ident: str) -> dict: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.11+, uv |
| Frontend | Next.js 14, React 18, Tailwind CSS |
| Database | SQLite (aiosqlite, WAL mode) |
| AI Scoring | Groq Cloud (Llama 3.3 70B Versatile) |
| Direct Downloads | Aria2 JSON-RPC |
| Torrents | Jackett + qBittorrent |
| Packaging | Docker Compose |

## License

MIT

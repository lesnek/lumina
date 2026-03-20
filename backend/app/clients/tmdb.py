import httpx

from app.models.schemas import TMDBMovie

API_BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(timeout=15)

    async def search_movie(self, title: str, language: str = "cs-CZ") -> list[TMDBMovie]:
        resp = await self._http.get(
            f"{API_BASE}/search/movie",
            params={
                "api_key": self._api_key,
                "query": title,
                "language": language,
                "include_adult": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        movies: list[TMDBMovie] = []
        for item in data.get("results", [])[:12]:
            release = item.get("release_date", "") or ""
            poster_path = item.get("poster_path")
            movies.append(
                TMDBMovie(
                    tmdb_id=item["id"],
                    title=item.get("title", ""),
                    original_title=item.get("original_title", ""),
                    year=release[:4] if len(release) >= 4 else "",
                    overview=item.get("overview", ""),
                    poster_url=f"{IMG_BASE}{poster_path}" if poster_path else None,
                )
            )
        return movies

    async def close(self) -> None:
        await self._http.aclose()

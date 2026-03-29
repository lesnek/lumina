import logging
import httpx
from typing import Optional, List

logger = logging.getLogger(__name__)


class SonarrClient:
    """Client for interacting with Sonarr API v3."""

    def __init__(self, api_url: str, api_key: str) -> None:
        self._url = api_url.rstrip("/")
        self._api_key = api_key
        self._http = httpx.AsyncClient(
            timeout=30,
            headers={"X-Api-Key": self._api_key},
        )

    async def get_series_by_tvdb_id(self, tvdb_id: int) -> Optional[dict]:
        """Check if a series exists in Sonarr by TVDB ID."""
        try:
            resp = await self._http.get(f"{self._url}/api/v3/series")
            if resp.status_code != 200:
                return None
            for s in resp.json():
                if s.get("tvdbId") == tvdb_id:
                    return s
            return None
        except Exception as e:
            logger.error("Sonarr lookup failed: %s", e)
            return None

    async def lookup_series(self, title: str) -> Optional[dict]:
        """Search Sonarr for a series by title."""
        try:
            resp = await self._http.get(
                f"{self._url}/api/v3/series/lookup",
                params={"term": title},
            )
            if resp.status_code == 200:
                results = resp.json()
                return results[0] if results else None
            return None
        except Exception as e:
            logger.error("Sonarr series lookup failed: %s", e)
            return None

    async def add_series(
        self, title: str, tvdb_id: int, root_folder: str, profile_id: int = 1
    ) -> bool:
        """Add a series to Sonarr."""
        try:
            lookup = await self.lookup_series(title)
            if not lookup:
                logger.warning("Sonarr: could not find '%s' for adding", title)
                return False

            payload = {
                **lookup,
                "rootFolderPath": root_folder,
                "qualityProfileId": profile_id,
                "monitored": True,
                "seasonFolder": True,
                "addOptions": {"searchForMissingEpisodes": False},
            }
            resp = await self._http.post(f"{self._url}/api/v3/series", json=payload)
            if resp.status_code in (200, 201):
                logger.info("Series '%s' added to Sonarr", title)
                return True
            else:
                logger.error("Sonarr add failed: %s", resp.text[:200])
                return False
        except Exception as e:
            logger.error("Sonarr add error: %s", e)
            return False

    async def trigger_import_scan(self, path: str) -> bool:
        """Trigger Sonarr to scan a folder for completed downloads."""
        try:
            payload = {
                "name": "DownloadedEpisodesScan",
                "path": path,
            }
            resp = await self._http.post(f"{self._url}/api/v3/command", json=payload)
            if resp.status_code in (200, 201, 202):
                logger.info("Sonarr scan triggered for: %s", path)
                return True
            return False
        except Exception as e:
            logger.error("Sonarr scan trigger failed: %s", e)
            return False

    async def get_root_folders(self) -> List[dict]:
        """Get configured root folders."""
        try:
            resp = await self._http.get(f"{self._url}/api/v3/rootfolder")
            return resp.json() if resp.status_code == 200 else []
        except Exception:
            return []

    async def get_quality_profiles(self) -> List[dict]:
        """Get quality profiles."""
        try:
            resp = await self._http.get(f"{self._url}/api/v3/qualityprofile")
            return resp.json() if resp.status_code == 200 else []
        except Exception:
            return []

    async def close(self) -> None:
        await self._http.aclose()

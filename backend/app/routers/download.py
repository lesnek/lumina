from fastapi import APIRouter, HTTPException

from app.config import get_effective_settings
from app.clients.aria2 import Aria2Client
from app.clients.qbittorrent import QBittorrentClient
from app.models.schemas import DownloadRequest
from app.sources.base import DownloadBackend
from app.sources.registry import SourceRegistry

router = APIRouter(prefix="/api", tags=["download"])


@router.post("/download")
async def start_download(req: DownloadRequest) -> dict:
    cfg = await get_effective_settings()
    target_dir = req.target_folder or cfg["plex_media_dir"]

    registry = SourceRegistry.get()
    source = registry.get_source_by_id(req.source_id) if req.source_id else None

    if source and source.download_backend == DownloadBackend.ARIA2:
        download_info = await source.get_download_info(req.file_ident)
        aria2 = Aria2Client(cfg["aria2_rpc_url"], cfg["aria2_rpc_secret"])
        try:
            gid = await aria2.add_uri(download_info["url"], directory=target_dir)
            return {
                "gid": gid,
                "status": "active",
                "target_dir": target_dir,
                "source": source.source_type.value,
            }
        finally:
            await aria2.close()

    elif source and source.download_backend == DownloadBackend.QBITTORRENT:
        if not req.magnet_url:
            raise HTTPException(400, "magnet_url is required for torrent downloads")
        if not cfg["qbittorrent_url"]:
            raise HTTPException(503, "qBittorrent is not configured")

        qbt = QBittorrentClient(
            cfg["qbittorrent_url"],
            cfg["qbittorrent_username"],
            cfg["qbittorrent_password"],
        )
        try:
            torrent_hash = await qbt.add_torrent(req.magnet_url, save_path=target_dir)
            return {
                "hash": torrent_hash,
                "status": "active",
                "target_dir": target_dir,
                "source": source.source_type.value,
            }
        finally:
            await qbt.close()

    raise HTTPException(400, f"Source not found (source_id={req.source_id})")


@router.get("/download/{gid}/status")
async def download_status(gid: str) -> dict:
    cfg = await get_effective_settings()
    aria2 = Aria2Client(cfg["aria2_rpc_url"], cfg["aria2_rpc_secret"])
    try:
        return await aria2.get_status(gid)
    finally:
        await aria2.close()


@router.get("/download/torrent/{torrent_hash}/status")
async def torrent_status(torrent_hash: str) -> dict:
    cfg = await get_effective_settings()
    if not cfg["qbittorrent_url"]:
        raise HTTPException(503, "qBittorrent is not configured")
    qbt = QBittorrentClient(
        cfg["qbittorrent_url"],
        cfg["qbittorrent_username"],
        cfg["qbittorrent_password"],
    )
    try:
        return await qbt.get_status(torrent_hash)
    finally:
        await qbt.close()

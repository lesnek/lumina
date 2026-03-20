import uuid

import httpx


class Aria2Client:
    def __init__(self, rpc_url: str, secret: str = "") -> None:
        self._rpc_url = rpc_url
        self._secret = secret
        self._http = httpx.AsyncClient(timeout=15)

    async def add_uri(self, uri: str, directory: str, filename: str = "") -> str:
        """Add a download to Aria2 and return the GID."""
        params: list = []
        if self._secret:
            params.append(f"token:{self._secret}")
        params.append([uri])

        options: dict[str, str] = {"dir": directory}
        if filename:
            options["out"] = filename
        params.append(options)

        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex[:8],
            "method": "aria2.addUri",
            "params": params,
        }
        resp = await self._http.post(self._rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Aria2 error: {data['error']}")
        return data["result"]

    async def get_status(self, gid: str) -> dict:
        params: list = []
        if self._secret:
            params.append(f"token:{self._secret}")
        params.append(gid)

        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex[:8],
            "method": "aria2.tellStatus",
            "params": params,
        }
        resp = await self._http.post(self._rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Aria2 error: {data['error']}")
        result = data["result"]
        return {
            "gid": result.get("gid", ""),
            "status": result.get("status", ""),
            "total_length": int(result.get("totalLength", 0)),
            "completed_length": int(result.get("completedLength", 0)),
            "download_speed": int(result.get("downloadSpeed", 0)),
        }

    async def close(self) -> None:
        await self._http.aclose()

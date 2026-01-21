"""Frigate API client for camera configuration."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.config import settings


@dataclass(frozen=True)
class FrigateCamera:
    name: str
    rtsp_url: str


class FrigateClient:
    """Async client for Frigate's REST API."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.frigate_url).rstrip("/")

    async def get_config(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/config"
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_cameras(self) -> List[FrigateCamera]:
        config = await self.get_config()
        cameras = config.get("cameras", {})
        if not isinstance(cameras, dict):
            return []

        results: List[FrigateCamera] = []
        for name, cam_config in cameras.items():
            rtsp_url = self._extract_rtsp(cam_config or {})
            if rtsp_url:
                results.append(
                    FrigateCamera(name=name, rtsp_url=self._normalize_rtsp_url(rtsp_url))
                )
        return results

    def _extract_rtsp(self, cam_config: Dict[str, Any]) -> Optional[str]:
        ffmpeg = cam_config.get("ffmpeg", {})
        inputs = ffmpeg.get("inputs", [])
        if not isinstance(inputs, list) or not inputs:
            return None

        # Prefer a recording-capable input when available.
        for input_cfg in inputs:
            roles = input_cfg.get("roles", []) if isinstance(input_cfg, dict) else []
            if isinstance(roles, list) and "record" in roles:
                return input_cfg.get("path")

        first = inputs[0] if isinstance(inputs[0], dict) else None
        return first.get("path") if first else None

    def _normalize_rtsp_url(self, rtsp_url: str) -> str:
        host_override = settings.frigate_rtsp_host.strip()
        if not host_override:
            return rtsp_url

        try:
            parts = urlsplit(rtsp_url)
        except Exception:
            return rtsp_url

        if parts.scheme not in ("rtsp", "rtsps") or not parts.netloc:
            return rtsp_url

        userinfo = None
        hostport = parts.netloc
        if "@" in parts.netloc:
            userinfo, hostport = parts.netloc.rsplit("@", 1)

        hostname = hostport
        port = ""
        if ":" in hostport:
            hostname, port = hostport.rsplit(":", 1)

        if hostname not in ("127.0.0.1", "localhost"):
            return rtsp_url

        new_hostport = host_override
        if port:
            new_hostport = f"{new_hostport}:{port}"

        new_netloc = f"{userinfo}@{new_hostport}" if userinfo else new_hostport
        return urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))


frigate_client = FrigateClient()

"""Frigate API client for camera configuration."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

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
                results.append(FrigateCamera(name=name, rtsp_url=rtsp_url))
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


frigate_client = FrigateClient()

"""go2rtc API client for stream management.

go2rtc is a high-performance streaming server that handles:
- RTSP to WebRTC/MJPEG/HLS conversion
- Efficient native video streaming with minimal CPU
- Automatic protocol negotiation and reconnection
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)


class StreamProducer(str, Enum):
    """Stream producer (source) types."""
    RTSP = "rtsp"
    RTMP = "rtmp"
    HTTP = "http"
    EXEC = "exec"


@dataclass
class StreamInfo:
    """Information about a go2rtc stream."""
    name: str
    url: str
    producers: List[Dict[str, Any]]
    consumers: List[Dict[str, Any]]

    @property
    def is_active(self) -> bool:
        """Check if stream has active producers."""
        return len(self.producers) > 0

    @property
    def consumer_count(self) -> int:
        """Number of active consumers (viewers)."""
        return len(self.consumers)


class Go2RTCError(Exception):
    """Base exception for go2rtc errors."""
    pass


class Go2RTCConnectionError(Go2RTCError):
    """Failed to connect to go2rtc."""
    pass


class Go2RTCAPIError(Go2RTCError):
    """go2rtc API returned an error."""
    pass


class Go2RTCClient:
    """Async client for go2rtc REST API.

    go2rtc API documentation: https://github.com/AlexxIT/go2rtc#api

    Usage:
        client = Go2RTCClient()
        await client.add_stream("camera1", "rtsp://user:pass@192.168.1.100:554/stream")
        info = await client.get_stream_info("camera1")
        await client.remove_stream("camera1")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        rtsp_port: Optional[int] = None,
        webrtc_port: Optional[int] = None,
        timeout: float = 10.0
    ):
        """Initialize go2rtc client.

        Args:
            host: go2rtc host (default: from GO2RTC_HOST env or localhost)
            port: go2rtc HTTP API port (default: from GO2RTC_PORT env or 8954)
            rtsp_port: go2rtc RTSP port (default: from GO2RTC_RTSP_PORT env or 8955)
            webrtc_port: go2rtc WebRTC port (default: from GO2RTC_WEBRTC_PORT env or 8956)
            timeout: Request timeout in seconds

        Note: Ports are offset from Frigate defaults (1984/8554/8555) to avoid conflicts.
        """
        self.host = host or os.getenv("GO2RTC_HOST", "localhost")
        self.port = port or int(os.getenv("GO2RTC_PORT", "8954"))
        self.rtsp_port = rtsp_port or int(os.getenv("GO2RTC_RTSP_PORT", "8955"))
        self.webrtc_port = webrtc_port or int(os.getenv("GO2RTC_WEBRTC_PORT", "8956"))
        self.timeout = timeout

        self._base_url = f"http://{self.host}:{self.port}"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self.timeout
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check if go2rtc is healthy and responding.

        Returns:
            True if go2rtc is responding, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/streams")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"go2rtc health check failed: {e}")
            return False

    async def add_stream(self, name: str, source_url: str) -> bool:
        """Add or update a stream in go2rtc.

        Args:
            name: Unique stream name (e.g., "camera_1")
            source_url: Source URL (e.g., "rtsp://user:pass@ip:554/stream")

        Returns:
            True if stream was added successfully

        Raises:
            Go2RTCAPIError: If the API returns an error
            Go2RTCConnectionError: If connection to go2rtc fails
        """
        try:
            client = await self._get_client()

            # go2rtc API: PUT /api/streams?name={name}&src={source}
            # Also supports POST for adding sources to existing streams
            response = await client.put(
                "/api/streams",
                params={"name": name, "src": source_url}
            )

            if response.status_code in (200, 201):
                logger.info(f"Added stream '{name}' to go2rtc")
                return True
            else:
                error_msg = f"Failed to add stream: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Go2RTCAPIError(error_msg)

        except httpx.RequestError as e:
            raise Go2RTCConnectionError(f"Failed to connect to go2rtc: {e}")

    async def remove_stream(self, name: str) -> bool:
        """Remove a stream from go2rtc.

        Args:
            name: Stream name to remove

        Returns:
            True if stream was removed (or didn't exist)

        Raises:
            Go2RTCConnectionError: If connection to go2rtc fails
        """
        try:
            client = await self._get_client()

            # go2rtc API: DELETE /api/streams?name={name}
            response = await client.delete(
                "/api/streams",
                params={"name": name}
            )

            if response.status_code in (200, 204, 404):
                logger.info(f"Removed stream '{name}' from go2rtc")
                return True
            else:
                logger.warning(f"Unexpected response removing stream: {response.status_code}")
                return False

        except httpx.RequestError as e:
            raise Go2RTCConnectionError(f"Failed to connect to go2rtc: {e}")

    async def get_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured streams.

        Returns:
            Dictionary of stream name -> stream info

        Raises:
            Go2RTCConnectionError: If connection to go2rtc fails
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/streams")

            if response.status_code == 200:
                return response.json() or {}
            else:
                logger.warning(f"Failed to get streams: {response.status_code}")
                return {}

        except httpx.RequestError as e:
            raise Go2RTCConnectionError(f"Failed to connect to go2rtc: {e}")

    async def get_stream_info(self, name: str) -> Optional[StreamInfo]:
        """Get information about a specific stream.

        Args:
            name: Stream name

        Returns:
            StreamInfo if stream exists, None otherwise

        Raises:
            Go2RTCConnectionError: If connection to go2rtc fails
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/streams", params={"name": name})

            if response.status_code == 200:
                data = response.json()
                if name in data:
                    stream_data = data[name]
                    return StreamInfo(
                        name=name,
                        url=stream_data.get("url", ""),
                        producers=stream_data.get("producers", []),
                        consumers=stream_data.get("consumers", [])
                    )
            return None

        except httpx.RequestError as e:
            raise Go2RTCConnectionError(f"Failed to connect to go2rtc: {e}")

    def get_stream_name(self, stream_id: int) -> str:
        """Generate consistent stream name from ID.

        Args:
            stream_id: Database stream ID

        Returns:
            Stream name for go2rtc (e.g., "camera_1")
        """
        return f"camera_{stream_id}"

    def get_webrtc_url(self, name: str, external_host: Optional[str] = None) -> str:
        """Get WebRTC streaming URL for a stream.

        Args:
            name: Stream name
            external_host: Optional external host for browser access

        Returns:
            WebRTC URL for embedding in iframe or opening directly
        """
        host = external_host or os.getenv("GO2RTC_EXTERNAL_HOST") or self.host
        return f"http://{host}:{self.port}/stream.html?src={name}"

    def get_webrtc_api_url(self, name: str, external_host: Optional[str] = None) -> str:
        """Get WebRTC API URL for custom video element integration.

        Args:
            name: Stream name
            external_host: Optional external host for browser access

        Returns:
            WebRTC API URL for custom integration
        """
        host = external_host or os.getenv("GO2RTC_EXTERNAL_HOST") or self.host
        return f"http://{host}:{self.port}/api/webrtc?src={name}"

    def get_mjpeg_url(self, name: str, external_host: Optional[str] = None) -> str:
        """Get MJPEG streaming URL for a stream.

        Args:
            name: Stream name
            external_host: Optional external host for browser access

        Returns:
            MJPEG stream URL for img tag or video player
        """
        host = external_host or os.getenv("GO2RTC_EXTERNAL_HOST") or self.host
        return f"http://{host}:{self.port}/api/stream.mjpeg?src={name}"

    def get_frame_url(self, name: str, external_host: Optional[str] = None) -> str:
        """Get single frame (snapshot) URL for a stream.

        Args:
            name: Stream name
            external_host: Optional external host for browser access

        Returns:
            JPEG snapshot URL
        """
        host = external_host or os.getenv("GO2RTC_EXTERNAL_HOST") or self.host
        return f"http://{host}:{self.port}/api/frame.jpeg?src={name}"

    def get_rtsp_url(self, name: str) -> str:
        """Get local RTSP restream URL.

        This URL can be used to get audio/video from go2rtc
        for processing (e.g., FFmpeg for audio extraction).

        Args:
            name: Stream name

        Returns:
            Local RTSP URL (always uses localhost for internal access)
        """
        return f"rtsp://localhost:{self.rtsp_port}/{name}"

    def get_hls_url(self, name: str, external_host: Optional[str] = None) -> str:
        """Get HLS streaming URL for a stream.

        Args:
            name: Stream name
            external_host: Optional external host for browser access

        Returns:
            HLS playlist URL
        """
        host = external_host or os.getenv("GO2RTC_EXTERNAL_HOST") or self.host
        return f"http://{host}:{self.port}/api/stream.m3u8?src={name}"


# Global client instance (initialized lazily)
_client: Optional[Go2RTCClient] = None


def get_go2rtc_client() -> Go2RTCClient:
    """Get global go2rtc client instance.

    Returns:
        Go2RTCClient instance
    """
    global _client
    if _client is None:
        _client = Go2RTCClient()
    return _client

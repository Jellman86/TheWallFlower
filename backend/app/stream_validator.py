"""Stream validation utilities using FFprobe."""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class StreamErrorType(str, Enum):
    """Categorized stream error types."""
    UNREACHABLE = "unreachable"
    AUTH_FAILED = "auth_failed"
    INVALID_URL = "invalid_url"
    CODEC_UNSUPPORTED = "codec_unsupported"
    NO_VIDEO_STREAM = "no_video_stream"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class StreamMetadata:
    """Validated stream metadata."""
    is_valid: bool
    error_type: Optional[StreamErrorType] = None
    error_message: Optional[str] = None

    # Video info
    codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None

    # Audio info
    has_audio: bool = False
    audio_codec: Optional[str] = None
    audio_sample_rate: Optional[int] = None


class StreamValidator:
    """Validates RTSP streams using FFprobe."""

    DEFAULT_TIMEOUT = 10  # seconds

    @classmethod
    async def validate(
        cls,
        rtsp_url: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> StreamMetadata:
        """Validate RTSP stream and extract metadata.

        Args:
            rtsp_url: The RTSP URL to validate
            timeout: Connection timeout in seconds

        Returns:
            StreamMetadata with validation results
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            cls._validate_sync,
            rtsp_url,
            timeout
        )

    @classmethod
    def _validate_sync(
        cls,
        rtsp_url: str,
        timeout: int
    ) -> StreamMetadata:
        """Synchronous validation implementation.

        Tries UDP first (default for RTSP), falls back to TCP if needed.
        """
        # Try UDP first (default), then TCP
        for transport in ["udp", "tcp"]:
            result = cls._try_ffprobe(rtsp_url, timeout, transport)
            if result.is_valid:
                return result
            # If auth failed or invalid URL, don't retry with different transport
            if result.error_type in [StreamErrorType.AUTH_FAILED, StreamErrorType.INVALID_URL]:
                return result

        # Return the last error (TCP attempt)
        return result

    @classmethod
    def _try_ffprobe(
        cls,
        rtsp_url: str,
        timeout: int,
        transport: str = "udp"
    ) -> StreamMetadata:
        """Try FFprobe with specific transport."""

        # Convert timeout to microseconds for RTSP-specific options
        timeout_us = str(timeout * 1000000)

        # Build FFprobe command with proper options
        # RTSP-specific options must come BEFORE the input URL
        ffprobe_cmd = [
            "ffprobe",
            "-v", "error",  # Only show errors (less noise)
            "-rtsp_transport", transport,
            "-stimeout", timeout_us,  # RTSP socket timeout (microseconds)
            "-analyzeduration", "5000000",  # 5 seconds analyze
            "-probesize", "5000000",  # 5MB probe
            "-print_format", "json",
            "-show_streams",
            rtsp_url
        ]

        # Log command (hide credentials in URL)
        safe_url = rtsp_url.split('@')[-1] if '@' in rtsp_url else rtsp_url
        logger.info(f"FFprobe validating ({transport}): rtsp://***@{safe_url}")

        try:
            result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10  # Extra buffer for subprocess
            )

            logger.debug(f"FFprobe returncode: {result.returncode}")
            if result.stderr:
                logger.info(f"FFprobe stderr ({transport}): {result.stderr[:500]}")

            if result.returncode != 0:
                return cls._parse_error(result.stderr, rtsp_url)

            # Check if we got valid JSON output
            if not result.stdout.strip():
                return StreamMetadata(
                    is_valid=False,
                    error_type=StreamErrorType.UNKNOWN,
                    error_message="No response from stream"
                )

            return cls._parse_metadata(result.stdout)

        except subprocess.TimeoutExpired:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.TIMEOUT,
                error_message=f"Connection timed out after {timeout} seconds"
            )
        except FileNotFoundError:
            logger.error("FFprobe not found in PATH")
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNKNOWN,
                error_message="FFprobe not installed"
            )
        except Exception as e:
            logger.error(f"FFprobe validation error: {e}")
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNKNOWN,
                error_message=str(e)
            )

    @classmethod
    def _parse_error(cls, stderr: str, url: str) -> StreamMetadata:
        """Parse FFprobe error output to categorize failure."""
        stderr_lower = stderr.lower()

        # Log the full error for debugging
        logger.debug(f"FFprobe error output: {stderr[:1000]}")

        # Check for authentication errors first (most specific)
        if "401" in stderr or "unauthorized" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.AUTH_FAILED,
                error_message="Authentication failed - check username/password"
            )

        # Check for timeout errors
        if "timeout" in stderr_lower or "timed out" in stderr_lower or "connection timed out" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.TIMEOUT,
                error_message="Connection timed out - camera may be slow or unreachable"
            )

        # Check for connection refused
        if "connection refused" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNREACHABLE,
                error_message="Connection refused - check IP address and port"
            )

        # Check for network unreachable
        if "no route" in stderr_lower or "network is unreachable" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNREACHABLE,
                error_message="Network unreachable - check network connectivity"
            )

        # Check for DNS resolution failures
        if "name or service not known" in stderr_lower or "could not resolve" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNREACHABLE,
                error_message="Cannot resolve hostname - check address"
            )

        # Check for invalid URL format
        if "invalid" in stderr_lower and "url" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.INVALID_URL,
                error_message="Invalid RTSP URL format"
            )

        # Check for 404 stream not found
        if "404" in stderr:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNREACHABLE,
                error_message="Stream path not found (404) - check stream path"
            )

        # Check for generic "not found" but not file not found
        if "stream not found" in stderr_lower or "method not found" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNREACHABLE,
                error_message="Stream not found - check stream path"
            )

        # Check for I/O errors (often indicates network issues)
        if "i/o error" in stderr_lower or "input/output error" in stderr_lower:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNREACHABLE,
                error_message="I/O error - connection interrupted"
            )

        # Extract first meaningful line of error for display
        error_lines = [line.strip() for line in stderr.strip().split('\n') if line.strip()]
        error_msg = error_lines[0][:200] if error_lines else "Unknown error"

        return StreamMetadata(
            is_valid=False,
            error_type=StreamErrorType.UNKNOWN,
            error_message=f"Connection failed: {error_msg}"
        )

    @classmethod
    def _parse_metadata(cls, stdout: str) -> StreamMetadata:
        """Parse FFprobe JSON output to extract metadata."""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.UNKNOWN,
                error_message="Failed to parse stream metadata"
            )

        streams = data.get("streams", [])
        video_stream = None
        audio_stream = None

        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream

        if not video_stream:
            return StreamMetadata(
                is_valid=False,
                error_type=StreamErrorType.NO_VIDEO_STREAM,
                error_message="No video stream found"
            )

        # Extract FPS from various formats
        fps = None
        if "r_frame_rate" in video_stream:
            try:
                num, den = video_stream["r_frame_rate"].split("/")
                if float(den) > 0:
                    fps = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass

        # Try avg_frame_rate as fallback
        if fps is None and "avg_frame_rate" in video_stream:
            try:
                num, den = video_stream["avg_frame_rate"].split("/")
                if float(den) > 0:
                    fps = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                pass

        # Extract bitrate
        bitrate = None
        if "bit_rate" in video_stream:
            try:
                bitrate = int(video_stream["bit_rate"])
            except (ValueError, TypeError):
                pass

        # Check for unsupported codecs
        codec_name = video_stream.get("codec_name", "").lower()
        if codec_name in ["hevc", "h265"]:
            logger.warning(f"H.265/HEVC codec detected - may have compatibility issues")

        return StreamMetadata(
            is_valid=True,
            codec=video_stream.get("codec_name"),
            width=video_stream.get("width"),
            height=video_stream.get("height"),
            fps=fps,
            bitrate=bitrate,
            has_audio=audio_stream is not None,
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else None
        )

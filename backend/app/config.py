"""Configuration management for TheWallflower.

Loads configuration from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///data/thewallflower.db"

    # WhisperLive connection
    whisper_host: str = "whisper-live"
    whisper_port: int = 9090

    # go2rtc configuration
    go2rtc_host: str = "localhost"
    go2rtc_port: int = 1984
    go2rtc_rtsp_port: int = 8554
    go2rtc_webrtc_port: int = 8555
    go2rtc_external_host: str = ""  # External host for browser access

    # Application
    log_level: str = "INFO"
    debug: bool = False

    # Video processing
    default_jpeg_quality: int = 80
    snapshot_interval: float = 5.0
    max_transcript_segments: int = 100

    # Stream worker
    rtsp_retry_count: int = 5
    rtsp_retry_delay: float = 2.0
    whisper_retry_delay: float = 5.0

    # Frontend
    frontend_path: str = "/app/frontend/dist"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings.

    Settings are loaded once and cached for the lifetime of the application.

    Returns:
        Settings object with values from environment variables.
    """
    return Settings(
        # Database
        database_url=os.getenv("DATABASE_URL", Settings.database_url),

        # WhisperLive
        whisper_host=os.getenv("WHISPER_HOST", Settings.whisper_host),
        whisper_port=int(os.getenv("WHISPER_PORT", str(Settings.whisper_port))),

        # go2rtc
        go2rtc_host=os.getenv("GO2RTC_HOST", Settings.go2rtc_host),
        go2rtc_port=int(os.getenv("GO2RTC_PORT", str(Settings.go2rtc_port))),
        go2rtc_rtsp_port=int(os.getenv(
            "GO2RTC_RTSP_PORT", str(Settings.go2rtc_rtsp_port)
        )),
        go2rtc_webrtc_port=int(os.getenv(
            "GO2RTC_WEBRTC_PORT", str(Settings.go2rtc_webrtc_port)
        )),
        go2rtc_external_host=os.getenv(
            "GO2RTC_EXTERNAL_HOST", Settings.go2rtc_external_host
        ),

        # Application
        log_level=os.getenv("LOG_LEVEL", Settings.log_level),
        debug=os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"),

        # Video processing
        default_jpeg_quality=int(os.getenv(
            "JPEG_QUALITY", str(Settings.default_jpeg_quality)
        )),
        snapshot_interval=float(os.getenv(
            "SNAPSHOT_INTERVAL", str(Settings.snapshot_interval)
        )),
        max_transcript_segments=int(os.getenv(
            "MAX_TRANSCRIPT_SEGMENTS", str(Settings.max_transcript_segments)
        )),

        # Stream worker
        rtsp_retry_count=int(os.getenv(
            "RTSP_RETRY_COUNT", str(Settings.rtsp_retry_count)
        )),
        rtsp_retry_delay=float(os.getenv(
            "RTSP_RETRY_DELAY", str(Settings.rtsp_retry_delay)
        )),
        whisper_retry_delay=float(os.getenv(
            "WHISPER_RETRY_DELAY", str(Settings.whisper_retry_delay)
        )),

        # Frontend
        frontend_path=os.getenv("FRONTEND_PATH", Settings.frontend_path),
    )


# Convenience accessor
settings = get_settings()

"""Database models for TheWallflower."""

import re
from datetime import datetime
from typing import Optional
from pydantic import field_validator
from sqlmodel import Field, SQLModel


class StreamConfigBase(SQLModel):
    """Base model for stream configuration."""
    name: str = Field(index=True)
    rtsp_url: str
    whisper_enabled: bool = Field(default=True)
    face_detection_enabled: bool = Field(default=False)  # Future use
    save_transcripts_to_file: bool = Field(default=False)  # Save transcripts to filesystem
    transcript_file_path: Optional[str] = Field(default=None)  # Custom path for transcripts

    @field_validator('rtsp_url')
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
        """Validate RTSP URL format."""
        v = v.strip()
        if not v:
            raise ValueError('RTSP URL is required')

        # Check for valid RTSP URL pattern
        rtsp_pattern = r'^rtsp://([^:]+:[^@]+@)?[\w\.\-]+:\d+/.+$|^rtsp://([^:]+:[^@]+@)?[\w\.\-]+/.+$'
        if not re.match(rtsp_pattern, v, re.IGNORECASE):
            # Also allow without explicit port
            simple_pattern = r'^rtsp://.*$'
            if not re.match(simple_pattern, v, re.IGNORECASE):
                raise ValueError(
                    'Invalid RTSP URL format. Expected: rtsp://[user:pass@]host[:port]/path'
                )

        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate stream name."""
        v = v.strip()
        if not v:
            raise ValueError('Stream name is required')
        if len(v) > 100:
            raise ValueError('Stream name must be less than 100 characters')
        return v


class StreamConfig(StreamConfigBase, table=True):
    """Stream configuration stored in database."""
    __tablename__ = "stream_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StreamConfigCreate(StreamConfigBase):
    """Schema for creating a new stream."""
    pass


class StreamConfigUpdate(SQLModel):
    """Schema for updating a stream (all fields optional)."""
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    whisper_enabled: Optional[bool] = None
    face_detection_enabled: Optional[bool] = None


class StreamConfigRead(StreamConfigBase):
    """Schema for reading a stream (includes id and timestamps)."""
    id: int
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Transcript Models
# =============================================================================

class TranscriptBase(SQLModel):
    """Base model for transcript segments."""
    stream_id: int = Field(foreign_key="stream_configs.id", index=True)
    text: str
    start_time: float  # Seconds from stream start
    end_time: float
    is_final: bool = Field(default=True)
    confidence: Optional[float] = Field(default=None)
    speaker_id: Optional[int] = Field(default=None)  # Future: link to Speaker table


class Transcript(TranscriptBase, table=True):
    """Transcript segment stored in database."""
    __tablename__ = "transcripts"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TranscriptRead(TranscriptBase):
    """Schema for reading a transcript."""
    id: int
    created_at: datetime


class TranscriptCreate(SQLModel):
    """Schema for creating a transcript (internal use)."""
    stream_id: int
    text: str
    start_time: float
    end_time: float
    is_final: bool = True
    confidence: Optional[float] = None
    speaker_id: Optional[int] = None

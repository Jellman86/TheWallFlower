"""Database models for TheWallflower."""

import re
from datetime import datetime
from typing import Optional
from pydantic import field_validator, ConfigDict
from sqlmodel import Field, SQLModel


class StreamConfigBase(SQLModel):
    """Base model for stream configuration."""
    name: str = Field(index=True)
    rtsp_url: str
    whisper_enabled: bool = Field(default=True)
    face_detection_enabled: bool = Field(default=False)
    face_detection_interval: int = Field(default=1)  # Seconds between checks (default 1s)
    save_transcripts_to_file: bool = Field(default=False)  # Save transcripts to filesystem
    transcript_file_path: Optional[str] = Field(default=None)  # Custom path for transcripts

    # Audio tuning settings (None = use global defaults from environment)
    audio_energy_threshold: Optional[float] = Field(default=None)  # RMS threshold for energy gating
    audio_vad_enabled: Optional[bool] = Field(default=None)  # Enable Silero VAD
    audio_vad_threshold: Optional[float] = Field(default=None)  # VAD speech probability threshold
    audio_vad_onset: Optional[float] = Field(default=None)  # VAD onset sensitivity
    audio_vad_offset: Optional[float] = Field(default=None)  # VAD offset sensitivity

    # Recording / NVR settings
    recording_enabled: bool = Field(default=False)
    recording_retention_days: int = Field(default=7)  # How many days to keep recordings


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
    face_detection_interval: Optional[int] = None
    save_transcripts_to_file: Optional[bool] = None
    transcript_file_path: Optional[str] = None
    # Audio tuning settings
    audio_energy_threshold: Optional[float] = None
    audio_vad_enabled: Optional[bool] = None
    audio_vad_threshold: Optional[float] = None
    audio_vad_onset: Optional[float] = None
    audio_vad_offset: Optional[float] = None
    
    recording_enabled: Optional[bool] = None
    recording_retention_days: Optional[int] = None


class StreamConfigRead(StreamConfigBase):
    """Schema for reading a stream (includes id and timestamps)."""
    id: int
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Face Recognition Models
# =============================================================================

class Face(SQLModel, table=True):
    """Known (or Unknown) face stored in the database."""
    __tablename__ = "faces"

    # Allow extra attributes for runtime embedding_numpy cache
    model_config = ConfigDict(extra='allow')

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="Unknown", index=True)
    embedding: bytes  # Serialized numpy array (float32, 512 dimensions)
    thumbnail_path: Optional[str] = Field(default=None)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

    # Simple boolean to mark if this face is 'known' (named by user)
    is_known: bool = Field(default=False)


class FaceRead(SQLModel):
    """Face response model (excludes binary embedding)."""
    id: int
    name: str
    thumbnail_path: Optional[str]
    first_seen: datetime
    last_seen: datetime
    is_known: bool


class FaceEvent(SQLModel, table=True):
    """Event when a face is detected in a stream."""
    __tablename__ = "face_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: int = Field(foreign_key="stream_configs.id", index=True)
    face_id: Optional[int] = Field(foreign_key="faces.id", default=None)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    confidence: float
    snapshot_path: Optional[str] = None  # Full frame snapshot where face was seen
    
    # Denormalized name for easier querying without join
    face_name: str = "Unknown"


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


# =============================================================================
# NVR / Recording Models
# =============================================================================

class Recording(SQLModel, table=True):
    """Video recording segment stored in database."""
    __tablename__ = "recordings"

    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: int = Field(foreign_key="stream_configs.id", index=True)
    
    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)
    duration_seconds: float
    
    file_path: str = Field(unique=True)  # Relative path: {stream_id}/{date}/{hour}/{file}.mp4
    file_size_bytes: int = Field(default=0)
    
    retention_locked: bool = Field(default=False)  # If True, auto-cleanup will skip this
    created_at: datetime = Field(default_factory=datetime.utcnow)

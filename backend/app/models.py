"""Database models for TheWallflower."""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class StreamConfigBase(SQLModel):
    """Base model for stream configuration."""
    name: str = Field(index=True)
    rtsp_url: str
    whisper_enabled: bool = Field(default=True)
    face_detection_enabled: bool = Field(default=False)  # Future use


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

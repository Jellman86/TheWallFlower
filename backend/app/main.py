"""TheWallflower - FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import settings
from app.db import init_db, get_session
from app.models import (
    StreamConfig,
    StreamConfigCreate,
    StreamConfigUpdate,
    StreamConfigRead,
)
from app.stream_manager import stream_manager
from app.worker import StreamStatus

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize database and start streams on startup."""
    init_db()
    logger.info("Database initialized")

    # Start all configured streams
    stream_manager.start_all()
    logger.info("Stream manager started")

    yield

    # Stop all streams on shutdown
    stream_manager.stop_all()
    logger.info("Stream manager stopped")


app = FastAPI(
    title="TheWallflower",
    description="Self-hosted NVR with real-time Speech-to-Text",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Stream Configuration CRUD Endpoints
# =============================================================================

@app.post("/api/streams", response_model=StreamConfigRead, status_code=201)
def create_stream(
    stream: StreamConfigCreate,
    session: Session = Depends(get_session)
) -> StreamConfig:
    """Create a new stream configuration and start the worker."""
    db_stream = StreamConfig.model_validate(stream)
    session.add(db_stream)
    session.commit()
    session.refresh(db_stream)

    # Auto-start the new stream
    stream_manager.start_stream(db_stream.id)

    return db_stream


@app.get("/api/streams", response_model=List[StreamConfigRead])
def list_streams(
    session: Session = Depends(get_session)
) -> List[StreamConfig]:
    """List all stream configurations."""
    statement = select(StreamConfig).order_by(StreamConfig.created_at.desc())
    streams = session.exec(statement).all()
    return streams


@app.get("/api/streams/{stream_id}", response_model=StreamConfigRead)
def get_stream(
    stream_id: int,
    session: Session = Depends(get_session)
) -> StreamConfig:
    """Get a specific stream configuration by ID."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    return stream


@app.patch("/api/streams/{stream_id}", response_model=StreamConfigRead)
def update_stream(
    stream_id: int,
    stream_update: StreamConfigUpdate,
    session: Session = Depends(get_session)
) -> StreamConfig:
    """Update a stream configuration and restart the worker if needed."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    update_data = stream_update.model_dump(exclude_unset=True)

    # Check if we need to restart the worker
    needs_restart = any(
        key in update_data for key in ["rtsp_url", "whisper_enabled"]
    )

    for key, value in update_data.items():
        setattr(stream, key, value)

    stream.updated_at = datetime.utcnow()
    session.add(stream)
    session.commit()
    session.refresh(stream)

    # Restart worker if configuration changed
    if needs_restart:
        stream_manager.restart_stream(stream_id)

    return stream


@app.delete("/api/streams/{stream_id}", status_code=204)
def delete_stream(
    stream_id: int,
    session: Session = Depends(get_session)
) -> None:
    """Delete a stream configuration and stop the worker."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    # Stop the worker first
    stream_manager.stop_stream(stream_id)

    session.delete(stream)
    session.commit()


# =============================================================================
# Stream Control Endpoints
# =============================================================================

@app.post("/api/streams/{stream_id}/start")
def start_stream(stream_id: int, session: Session = Depends(get_session)):
    """Start a stream worker."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    success = stream_manager.start_stream(stream_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start stream")

    return {"status": "started", "stream_id": stream_id}


@app.post("/api/streams/{stream_id}/stop")
def stop_stream(stream_id: int, session: Session = Depends(get_session)):
    """Stop a stream worker."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    stream_manager.stop_stream(stream_id)
    return {"status": "stopped", "stream_id": stream_id}


@app.post("/api/streams/{stream_id}/restart")
def restart_stream(stream_id: int, session: Session = Depends(get_session)):
    """Restart a stream worker."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    success = stream_manager.restart_stream(stream_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to restart stream")

    return {"status": "restarted", "stream_id": stream_id}


# =============================================================================
# Stream Status Endpoints
# =============================================================================

@app.get("/api/streams/{stream_id}/status")
def get_stream_status(stream_id: int, session: Session = Depends(get_session)) -> Dict[str, Any]:
    """Get the status of a specific stream."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    status = stream_manager.get_status(stream_id)
    if status:
        return {
            "stream_id": status.stream_id,
            "is_running": status.is_running,
            "video_connected": status.video_connected,
            "audio_connected": status.audio_connected,
            "whisper_connected": status.whisper_connected,
            "fps": round(status.fps, 1),
            "error": status.error,
        }
    else:
        return {
            "stream_id": stream_id,
            "is_running": False,
            "video_connected": False,
            "audio_connected": False,
            "whisper_connected": False,
            "fps": 0,
            "error": None,
        }


@app.get("/api/status")
def get_all_status() -> Dict[str, Any]:
    """Get status of all streams."""
    statuses = stream_manager.get_all_statuses()
    return {
        "streams": {
            str(stream_id): {
                "is_running": status.is_running,
                "video_connected": status.video_connected,
                "whisper_connected": status.whisper_connected,
                "fps": round(status.fps, 1),
                "error": status.error,
            }
            for stream_id, status in statuses.items()
        },
        "total_active": len(statuses),
    }


# =============================================================================
# Video Streaming Endpoints
# =============================================================================

@app.get("/api/video/{stream_id}")
async def video_stream(stream_id: int):
    """MJPEG video stream for a specific camera."""
    worker = stream_manager.get_worker(stream_id)
    if not worker or not worker.mjpeg_streamer:
        raise HTTPException(status_code=404, detail="Stream not found or not running")

    async def generate():
        """Generate MJPEG frames."""
        streamer = worker.mjpeg_streamer
        while True:
            frame = await streamer.get_frame()
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/snapshot/{stream_id}")
async def get_snapshot(stream_id: int):
    """Get a single JPEG snapshot from a stream."""
    worker = stream_manager.get_worker(stream_id)
    if not worker or not worker.mjpeg_streamer:
        raise HTTPException(status_code=404, detail="Stream not found or not running")

    frame = worker.mjpeg_streamer.current_frame
    if not frame:
        raise HTTPException(status_code=503, detail="No frame available")

    return StreamingResponse(
        iter([frame]),
        media_type="image/jpeg"
    )


# =============================================================================
# Transcript Endpoints
# =============================================================================

@app.get("/api/streams/{stream_id}/transcripts")
def get_transcripts(stream_id: int, limit: int = 50) -> Dict[str, Any]:
    """Get recent transcripts for a stream."""
    worker = stream_manager.get_worker(stream_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Stream not found or not running")

    transcripts = worker.transcripts[-limit:]
    return {
        "stream_id": stream_id,
        "transcripts": [
            {
                "text": t.text,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "is_final": t.is_final,
            }
            for t in transcripts
        ],
        "count": len(transcripts),
    }


# =============================================================================
# Health Check
# =============================================================================

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "thewallflower"}


# =============================================================================
# Static File Serving (Frontend)
# =============================================================================

# Mount the frontend build directory - this will be populated by the build process
frontend_path = Path(settings.frontend_path)
if frontend_path.exists():
    logger.info(f"Serving frontend from: {frontend_path}")
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    logger.warning(f"Frontend not found at {frontend_path}, API-only mode")

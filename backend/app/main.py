"""TheWallflower - FastAPI Application."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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
from app.worker import StreamStatus, ConnectionState, CircuitBreakerState
from app.stream_validator import StreamValidator, StreamMetadata, StreamErrorType
from app.services.transcript_service import transcript_service
from app.services.event_broadcaster import event_broadcaster, StreamEvent
from app.models import Transcript, TranscriptRead
from app.routers import debug as debug_router

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

# Include routers
app.include_router(debug_router.router)


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


@app.post("/api/streams/test-connection")
async def test_rtsp_connection(rtsp_url: str, timeout: int = 10):
    """Test if an RTSP URL is accessible with detailed diagnostics.

    Uses FFprobe for validation with proper timeout support.
    Returns detailed error categorization and stream metadata.
    """
    # Validate with FFprobe (has proper timeout)
    metadata = await StreamValidator.validate(rtsp_url, timeout=timeout)

    # Build debug info
    debug_info = {
        "command": metadata.debug_command,
        "transport": metadata.debug_transport,
        "stderr": metadata.debug_stderr,
        "stdout": metadata.debug_stdout[:500] if metadata.debug_stdout else None,
    }

    if not metadata.is_valid:
        return {
            "success": False,
            "error": metadata.error_message,
            "error_type": metadata.error_type.value if metadata.error_type else "unknown",
            "metadata": None,
            "debug": debug_info
        }

    # Return success with full metadata
    return {
        "success": True,
        "message": "Connection successful",
        "error": None,
        "error_type": None,
        "metadata": {
            "resolution": f"{metadata.width}x{metadata.height}",
            "codec": metadata.codec,
            "fps": round(metadata.fps, 1) if metadata.fps else None,
            "bitrate_kbps": metadata.bitrate // 1000 if metadata.bitrate else None,
            "has_audio": metadata.has_audio,
            "audio_codec": metadata.audio_codec
        },
        "debug": debug_info
    }


@app.get("/api/streams/{stream_id}/diagnostics")
async def get_stream_diagnostics(stream_id: int, session: Session = Depends(get_session)):
    """Get detailed diagnostics for a stream including metadata and connection history."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    worker = stream_manager.get_worker(stream_id)

    # Get fresh metadata via FFprobe
    metadata = await StreamValidator.validate(stream.rtsp_url, timeout=10)

    response = {
        "stream_id": stream_id,
        "name": stream.name,
        "validation": {
            "is_valid": metadata.is_valid,
            "error_type": metadata.error_type.value if metadata.error_type else None,
            "error_message": metadata.error_message
        },
        "metadata": None,
        "worker_status": None
    }

    if metadata.is_valid:
        response["metadata"] = {
            "codec": metadata.codec,
            "resolution": f"{metadata.width}x{metadata.height}",
            "fps": round(metadata.fps, 1) if metadata.fps else None,
            "bitrate_kbps": metadata.bitrate // 1000 if metadata.bitrate else None,
            "has_audio": metadata.has_audio,
            "audio_codec": metadata.audio_codec,
            "audio_sample_rate": metadata.audio_sample_rate
        }

    if worker:
        status = worker.status
        response["worker_status"] = {
            "is_running": status.is_running,
            "video_connected": status.video_connected,
            "video_thread_alive": status.video_thread_alive,
            "audio_thread_alive": status.audio_thread_alive,
            "fps": round(status.fps, 1),
            "retry_count": status.retry_count,
            "consecutive_failures": status.consecutive_failures,
            "last_frame_time": status.last_frame_time.isoformat() if status.last_frame_time else None,
            "last_successful_connection": status.last_successful_connection.isoformat() if status.last_successful_connection else None,
            "ffmpeg_restarts": status.ffmpeg_restarts,
            "whisper_reconnects": status.whisper_reconnects,
            "connection_state": status.connection_state.value,
            "circuit_breaker_state": status.circuit_breaker_state.value,
            "error": status.error
        }

    return response


@app.post("/api/streams/{stream_id}/force-retry")
def force_retry_stream(stream_id: int, session: Session = Depends(get_session)):
    """Force a stream to retry connection immediately, resetting circuit breaker."""
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    success = stream_manager.force_retry(stream_id)
    if not success:
        raise HTTPException(status_code=400, detail="Stream not running")

    return {"status": "retry_triggered", "stream_id": stream_id}


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
            # Enhanced connection tracking
            "connection_state": status.connection_state.value,
            "retry_count": status.retry_count,
            "next_retry_time": status.next_retry_time.isoformat() if status.next_retry_time else None,
            "circuit_breaker_state": status.circuit_breaker_state.value,
            "consecutive_failures": status.consecutive_failures,
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
            # Enhanced connection tracking
            "connection_state": ConnectionState.STOPPED.value,
            "retry_count": 0,
            "next_retry_time": None,
            "circuit_breaker_state": CircuitBreakerState.CLOSED.value,
            "consecutive_failures": 0,
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
                "connection_state": status.connection_state.value,
                "retry_count": status.retry_count,
                "circuit_breaker_state": status.circuit_breaker_state.value,
            }
            for stream_id, status in statuses.items()
        },
        "total_active": len(statuses),
    }


# =============================================================================
# go2rtc Streaming URLs
# =============================================================================

@app.get("/api/streams/{stream_id}/urls")
def get_stream_urls(stream_id: int, session: Session = Depends(get_session)) -> Dict[str, Any]:
    """Get go2rtc streaming URLs for a stream.

    Returns URLs for different streaming protocols:
    - webrtc: Low-latency WebRTC stream (recommended for live viewing)
    - mjpeg: MJPEG stream for compatibility
    - frame: Single frame snapshot
    - hls: HLS stream for wider compatibility

    Args:
        stream_id: Stream ID to get URLs for

    Returns:
        Dictionary with URLs for each protocol
    """
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    # Get URLs from stream manager
    urls = stream_manager.get_stream_urls(stream_id)

    return {
        "stream_id": stream_id,
        "stream_name": stream.name,
        "urls": urls,
        "recommended": "webrtc"  # WebRTC has lowest latency
    }


@app.get("/api/go2rtc/status")
async def get_go2rtc_status() -> Dict[str, Any]:
    """Get go2rtc health status and configured streams.

    Returns:
        go2rtc status and list of configured streams
    """
    try:
        is_healthy = await stream_manager.go2rtc.health_check()
        streams = await stream_manager.go2rtc.get_streams() if is_healthy else {}
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "host": settings.go2rtc_host,
            "port": settings.go2rtc_port,
            "streams": streams,
            "stream_count": len(streams)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "host": settings.go2rtc_host,
            "port": settings.go2rtc_port,
            "streams": {},
            "stream_count": 0
        }


# =============================================================================
# Video Streaming Endpoints (Proxied through go2rtc)
# =============================================================================

@app.get("/api/streams/{stream_id}/mjpeg")
async def stream_mjpeg_proxy(stream_id: int, fps: int = 10, height: int = 720):
    """Proxy MJPEG stream from go2rtc.

    This endpoint proxies the MJPEG stream from go2rtc so it works
    through reverse proxies and HTTPS without mixed content issues.

    Args:
        stream_id: Stream ID to view
        fps: Max frames per second (default 10)
        height: Max height in pixels (default 720)
    """
    import httpx

    worker = stream_manager.get_worker(stream_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Stream not found")

    if not worker.status.is_running:
        raise HTTPException(status_code=404, detail="Stream not running")

    # Build go2rtc MJPEG URL (internal, localhost)
    stream_name = f"camera_{stream_id}"
    go2rtc_url = f"http://localhost:{settings.go2rtc_port}/api/stream.mjpeg?src={stream_name}&fps={fps}&height={height}"

    async def proxy_stream():
        """Proxy the MJPEG stream from go2rtc."""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", go2rtc_url) as response:
                    if response.status_code != 200:
                        logger.error(f"go2rtc returned {response.status_code} for stream {stream_id}")
                        return
                    async for chunk in response.aiter_bytes(chunk_size=32768):
                        yield chunk
        except httpx.ConnectError:
            logger.error(f"Failed to connect to go2rtc for stream {stream_id}")
        except Exception as e:
            logger.error(f"MJPEG proxy error for stream {stream_id}: {e}")

    return StreamingResponse(
        proxy_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


@app.get("/api/streams/{stream_id}/frame")
async def stream_frame_proxy(stream_id: int):
    """Proxy single frame (snapshot) from go2rtc.

    Args:
        stream_id: Stream ID to get frame from
    """
    import httpx

    worker = stream_manager.get_worker(stream_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Stream not found")

    if not worker.status.is_running:
        raise HTTPException(status_code=404, detail="Stream not running")

    # Build go2rtc frame URL (internal, localhost)
    stream_name = f"camera_{stream_id}"
    go2rtc_url = f"http://localhost:{settings.go2rtc_port}/api/frame.jpeg?src={stream_name}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(go2rtc_url)
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to get frame from go2rtc")
            return StreamingResponse(
                iter([response.content]),
                media_type="image/jpeg"
            )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="go2rtc not available")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout getting frame")


# =============================================================================
# Transcript Endpoints
# =============================================================================

@app.get("/api/streams/{stream_id}/transcripts")
def get_transcripts(stream_id: int, limit: int = 50) -> Dict[str, Any]:
    """Get recent transcripts for a stream (real-time from memory).

    For live/real-time transcripts while stream is running.
    Use /api/transcripts for historical transcripts from database.
    """
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


@app.get("/api/transcripts")
def get_transcripts_history(
    stream_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Get historical transcripts from database.

    Args:
        stream_id: Filter by stream ID (optional)
        limit: Maximum number of transcripts to return (default 50, max 500)
        offset: Number of transcripts to skip for pagination
        search: Search query to filter transcripts by text content

    Returns:
        Paginated list of transcripts with metadata
    """
    from typing import Optional as Opt

    limit = min(limit, 500)  # Cap at 500

    if search:
        transcripts = transcript_service.search(
            query=search,
            stream_id=stream_id,
            limit=limit,
            offset=offset,
        )
    elif stream_id is not None:
        transcripts = transcript_service.get_by_stream(
            stream_id=stream_id,
            limit=limit,
            offset=offset,
            final_only=True,
        )
    else:
        # Get from all streams - need to implement this
        from sqlmodel import select, col
        from app.db import engine
        with Session(engine) as session:
            statement = select(Transcript).where(Transcript.is_final == True)
            statement = statement.order_by(col(Transcript.created_at).desc())
            statement = statement.offset(offset).limit(limit)
            transcripts = list(session.exec(statement).all())

    return {
        "transcripts": [
            {
                "id": t.id,
                "stream_id": t.stream_id,
                "text": t.text,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "is_final": t.is_final,
                "speaker_id": t.speaker_id,
                "created_at": t.created_at.isoformat(),
            }
            for t in transcripts
        ],
        "count": len(transcripts),
        "limit": limit,
        "offset": offset,
        "has_more": len(transcripts) == limit,
    }


@app.get("/api/transcripts/export")
def export_transcripts(
    stream_id: int,
    format: str = "json",
) -> Any:
    """Export all transcripts for a stream.

    Args:
        stream_id: Stream ID to export transcripts for
        format: Export format - 'json', 'txt', 'srt', or 'vtt'

    Returns:
        Transcripts in the requested format
    """
    # Get all transcripts for this stream
    transcripts = transcript_service.get_by_stream(
        stream_id=stream_id,
        limit=10000,  # Get all
        final_only=True,
    )

    if format == "txt":
        # Plain text format
        content = "\n".join(t.text for t in reversed(transcripts))
        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=transcripts_{stream_id}.txt"}
        )

    elif format == "srt":
        # SubRip subtitle format
        lines = []
        for i, t in enumerate(reversed(transcripts), 1):
            start_h, start_m = divmod(int(t.start_time), 3600), divmod(int(t.start_time) % 3600, 60)
            start_s = t.start_time % 60
            end_h, end_m = divmod(int(t.end_time), 3600), divmod(int(t.end_time) % 3600, 60)
            end_s = t.end_time % 60

            lines.append(str(i))
            lines.append(
                f"{start_h[0]:02d}:{start_m[0]:02d}:{start_s:06.3f}".replace(".", ",") +
                " --> " +
                f"{end_h[0]:02d}:{end_m[0]:02d}:{end_s:06.3f}".replace(".", ",")
            )
            lines.append(t.text)
            lines.append("")

        content = "\n".join(lines)
        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=transcripts_{stream_id}.srt"}
        )

    elif format == "vtt":
        # WebVTT subtitle format
        lines = ["WEBVTT", ""]
        for t in reversed(transcripts):
            start_h, start_m = divmod(int(t.start_time), 3600), divmod(int(t.start_time) % 3600, 60)
            start_s = t.start_time % 60
            end_h, end_m = divmod(int(t.end_time), 3600), divmod(int(t.end_time) % 3600, 60)
            end_s = t.end_time % 60

            lines.append(
                f"{start_h[0]:02d}:{start_m[0]:02d}:{start_s:06.3f}" +
                " --> " +
                f"{end_h[0]:02d}:{end_m[0]:02d}:{end_s:06.3f}"
            )
            lines.append(t.text)
            lines.append("")

        content = "\n".join(lines)
        return StreamingResponse(
            iter([content]),
            media_type="text/vtt",
            headers={"Content-Disposition": f"attachment; filename=transcripts_{stream_id}.vtt"}
        )

    else:
        # JSON format (default)
        return {
            "stream_id": stream_id,
            "transcripts": [
                {
                    "id": t.id,
                    "text": t.text,
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                    "speaker_id": t.speaker_id,
                    "created_at": t.created_at.isoformat(),
                }
                for t in reversed(transcripts)
            ],
            "count": len(transcripts),
        }


@app.get("/api/transcripts/stats")
def get_transcript_stats(stream_id: Optional[int] = None) -> Dict[str, Any]:
    """Get transcript statistics.

    Args:
        stream_id: Optional stream ID to get stats for

    Returns:
        Statistics about transcripts
    """
    from sqlmodel import select, func, col
    from app.db import engine

    with Session(engine) as session:
        if stream_id is not None:
            total = transcript_service.count_by_stream(stream_id)
            return {
                "stream_id": stream_id,
                "total_transcripts": total,
            }
        else:
            # Get stats for all streams
            statement = select(
                Transcript.stream_id,
                func.count(Transcript.id).label("count")
            ).group_by(Transcript.stream_id)
            results = session.exec(statement).all()

            return {
                "streams": [
                    {"stream_id": r[0], "count": r[1]}
                    for r in results
                ],
                "total_transcripts": sum(r[1] for r in results),
            }


@app.delete("/api/transcripts/cleanup")
def cleanup_transcripts(
    max_age_days: int = 30,
    stream_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Clean up old transcripts.

    Args:
        max_age_days: Delete transcripts older than this many days (default 30)
        stream_id: If provided, delete all transcripts for this stream

    Returns:
        Number of transcripts deleted
    """
    if stream_id is not None:
        deleted = transcript_service.delete_by_stream(stream_id)
        return {
            "deleted": deleted,
            "stream_id": stream_id,
            "message": f"Deleted all transcripts for stream {stream_id}",
        }
    else:
        deleted = transcript_service.cleanup_old(max_age_days=max_age_days)
        return {
            "deleted": deleted,
            "max_age_days": max_age_days,
            "message": f"Deleted transcripts older than {max_age_days} days",
        }


# =============================================================================
# Server-Sent Events (SSE)
# =============================================================================

@app.get("/api/events")
async def global_events():
    """SSE endpoint for all stream events.

    Streams real-time updates for all streams including:
    - status: Stream status changes (connected, fps, etc.)
    - transcript: New transcript segments
    - error: Error notifications

    Usage:
        const eventSource = new EventSource('/api/events');
        eventSource.addEventListener('status', (e) => console.log(JSON.parse(e.data)));
        eventSource.addEventListener('transcript', (e) => console.log(JSON.parse(e.data)));
    """
    async def event_generator():
        queue = await event_broadcaster.subscribe(stream_id=None)
        try:
            # Send initial connection event
            yield "event: connected\ndata: {\"message\": \"Connected to event stream\"}\n\n"

            while True:
                try:
                    # Wait for events with timeout for keepalive
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await event_broadcaster.unsubscribe(queue, stream_id=None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.get("/api/streams/{stream_id}/events")
async def stream_events(stream_id: int):
    """SSE endpoint for a specific stream's events.

    Streams real-time updates for a single stream including:
    - status: Stream status changes
    - transcript: New transcript segments
    - error: Error notifications

    Args:
        stream_id: The stream to subscribe to
    """
    # Verify stream exists
    with Session(engine) as session:
        stream = session.get(StreamConfig, stream_id)
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")

    async def event_generator():
        queue = await event_broadcaster.subscribe(stream_id=stream_id)
        try:
            # Send initial connection event with current status
            worker = stream_manager.get_worker(stream_id)
            if worker:
                status = worker.status
                initial_status = {
                    "type": "status",
                    "stream_id": stream_id,
                    "data": {
                        "is_running": status.is_running,
                        "video_connected": status.video_connected,
                        "audio_connected": status.audio_connected,
                        "whisper_connected": status.whisper_connected,
                        "fps": status.fps,
                        "error": status.error,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
                yield f"event: status\ndata: {json.dumps(initial_status)}\n\n"
            else:
                yield "event: connected\ndata: {\"message\": \"Connected, stream not running\"}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await event_broadcaster.unsubscribe(queue, stream_id=stream_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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

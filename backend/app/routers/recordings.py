from typing import List, Optional
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select, func

from app.db import get_session
from app.models import Recording, StreamConfig
from app.services.recording_service import recording_service

router = APIRouter(tags=["recordings"])

@router.get("/api/streams/{stream_id}/recordings", response_model=List[Recording])
def list_recordings(
    stream_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    session: Session = Depends(get_session)
):
    """List recordings for a stream within a time range."""
    # Verify stream exists
    stream = session.get(StreamConfig, stream_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
        
    return recording_service.get_recordings(stream_id, start_time, end_time)

@router.get("/api/streams/{stream_id}/recordings/dates", response_model=List[str])
def list_recording_dates(
    stream_id: int,
    session: Session = Depends(get_session)
):
    """Get a list of dates (YYYY-MM-DD) that have recordings."""
    # SQLite specific date extraction
    # This might need adjustment if DB engine changes, but we are using SQLite.
    statement = select(
        func.strftime('%Y-%m-%d', Recording.start_time).label('date')
    ).where(
        Recording.stream_id == stream_id
    ).distinct().order_by('date')
    
    results = session.exec(statement).all()
    return results

@router.get("/api/recordings/{recording_id}/stream")
def stream_recording(
    recording_id: int,
    session: Session = Depends(get_session)
):
    """Stream a specific recording file (supports HTTP Range requests)."""
    rec = session.get(Recording, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    full_path = Path("/data/recordings") / rec.file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Recording file not found on disk")

    # FileResponse handles Range headers automatically for seeking
    return FileResponse(
        path=full_path, 
        media_type="video/mp4", 
        filename=full_path.name
    )

@router.get("/api/recordings/{recording_id}")
def get_recording(
    recording_id: int,
    session: Session = Depends(get_session)
):
    """Get metadata for a single recording."""
    rec = session.get(Recording, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")
    return rec

@router.delete("/api/recordings/{recording_id}")
def delete_recording(
    recording_id: int,
    session: Session = Depends(get_session)
):
    """Delete a recording (file + DB)."""
    rec = session.get(Recording, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Delete file
    try:
        full_path = Path("/data/recordings") / rec.file_path
        if full_path.exists():
            full_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")

    # Delete DB record
    session.delete(rec)
    session.commit()
    
    return {"status": "deleted", "id": recording_id}

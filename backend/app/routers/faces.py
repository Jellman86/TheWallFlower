"""Faces API router."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, col
from datetime import datetime
import os

from app.db import get_session
from app.models import Face, FaceEvent

router = APIRouter(prefix="/api/faces", tags=["faces"])

@router.get("", response_model=List[Face])
def list_faces(
    known: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session)
):
    """List detected faces."""
    statement = select(Face)
    
    if known is not None:
        statement = statement.where(Face.is_known == known)
        
    # Sort by last seen descending (newest first)
    statement = statement.order_by(col(Face.last_seen).desc())
    statement = statement.offset(offset).limit(limit)
    
    return session.exec(statement).all()

@router.get("/{face_id}", response_model=Face)
def get_face(face_id: int, session: Session = Depends(get_session)):
    """Get a specific face."""
    face = session.get(Face, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    return face

@router.patch("/{face_id}", response_model=Face)
def update_face(
    face_id: int, 
    name: str = Query(None),
    is_known: bool = Query(None),
    session: Session = Depends(get_session)
):
    """Update face name and known status."""
    face = session.get(Face, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    
    if name is not None:
        face.name = name
    
    if is_known is not None:
        face.is_known = is_known
    
    session.add(face)
    session.commit()
    session.refresh(face)
    return face

@router.delete("/{face_id}")
def delete_face(face_id: int, session: Session = Depends(get_session)):
    """Delete a face and its thumbnail."""
    face = session.get(Face, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    
    # Remove thumbnail file
    if face.thumbnail_path and os.path.exists(face.thumbnail_path):
        try:
            os.remove(face.thumbnail_path)
        except Exception as e:
            # Log but continue
            pass
            
    # Remove events associated with this face (or set to unknown/null?)
    # For now, cascade delete manually or set to null if foreign key doesn't cascade
    events = session.exec(select(FaceEvent).where(FaceEvent.face_id == face_id)).all()
    for event in events:
        session.delete(event)
        
    session.delete(face)
    session.commit()
    return {"status": "deleted", "id": face_id}

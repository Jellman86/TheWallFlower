"""Faces API router."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body, BackgroundTasks
from sqlmodel import Session, select, col, func
from datetime import datetime
import os
import pickle
import numpy as np
import logging

from app.db import get_session
from app.models import Face, FaceRead, FaceEvent, FaceEmbedding
from app.services.detection.face_service import face_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/faces", tags=["faces"])

class FacePagination(BaseModel):
    items: List[FaceRead]
    total: int
    limit: int
    offset: int
    has_more: bool


class FaceGroupMember(BaseModel):
    """A face within a group."""
    id: int
    thumbnail_path: Optional[str]
    first_seen: datetime
    last_seen: datetime
    embedding_count: int


class FaceGroup(BaseModel):
    """Group of faces with the same name."""
    name: str
    is_known: bool
    face_count: int
    total_embeddings: int
    first_seen: datetime
    last_seen: datetime
    primary_face_id: int  # The face with most embeddings (best for thumbnail)
    primary_thumbnail: Optional[str]
    faces: List[FaceGroupMember]


class GroupedFacesResponse(BaseModel):
    """Response for grouped faces view."""
    groups: List[FaceGroup]
    total_groups: int
    total_faces: int


class MergeFacesRequest(BaseModel):
    """Request to merge multiple faces into one."""
    face_ids: List[int]
    target_name: str
    keep_face_id: Optional[int] = None  # Optional: specific face to keep as primary


class MergeFacesResponse(BaseModel):
    """Response from merge operation."""
    merged_face_id: int
    merged_count: int
    total_embeddings: int
    name: str


class KnownName(BaseModel):
    """A known face name for autocomplete."""
    name: str
    face_id: int
    embedding_count: int
    thumbnail_path: Optional[str]

class EventPagination(BaseModel):
    items: List[FaceEvent]
    total: int
    limit: int
    offset: int
    has_more: bool

@router.get("", response_model=FacePagination)
def list_faces(
    known: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session)
):
    """List detected faces with pagination."""
    statement = select(Face)
    count_statement = select(func.count()).select_from(Face)

    if known is not None:
        statement = statement.where(Face.is_known == known)
        count_statement = count_statement.where(Face.is_known == known)

    total = session.exec(count_statement).one()

    # Sort by last seen descending (newest first)
    statement = statement.order_by(col(Face.last_seen).desc())
    statement = statement.offset(offset).limit(limit)
    items = session.exec(statement).all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total
    }

@router.get("/{face_id}", response_model=FaceRead)
def get_face(face_id: int, session: Session = Depends(get_session)):
    """Get a specific face."""
    face = session.get(Face, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    return face

@router.patch("/{face_id}", response_model=FaceRead)
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

@router.get("/{face_id}/embeddings", response_model=List[dict])
def list_face_embeddings(
    face_id: int,
    session: Session = Depends(get_session)
):
    """List all embeddings for a face."""
    from app.models import FaceEmbedding
    statement = select(FaceEmbedding).where(FaceEmbedding.face_id == face_id)
    statement = statement.order_by(col(FaceEmbedding.created_at).desc())
    
    results = session.exec(statement).all()
    
    # Return as dict to exclude binary embedding and include image URL if possible
    return [
        {
            "id": e.id,
            "created_at": e.created_at,
            "source": e.source,
            "quality_score": e.quality_score,
            "image_path": e.image_path
        }
        for e in results
    ]

@router.get("/events/all", response_model=EventPagination)
def list_face_events(
    face_id: Optional[int] = None,
    stream_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session)
):
    """List face detection events with pagination."""
    statement = select(FaceEvent)
    count_statement = select(func.count()).select_from(FaceEvent)

    if face_id is not None:
        statement = statement.where(FaceEvent.face_id == face_id)
        count_statement = count_statement.where(FaceEvent.face_id == face_id)

    if stream_id is not None:
        statement = statement.where(FaceEvent.stream_id == stream_id)
        count_statement = count_statement.where(FaceEvent.stream_id == stream_id)

    total = session.exec(count_statement).one()

    # Sort by timestamp descending (newest first)
    statement = statement.order_by(col(FaceEvent.timestamp).desc())
    statement = statement.offset(offset).limit(limit)
    items = session.exec(statement).all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total
    }


# =============================================================================
# Grouping, Merging, and Names Endpoints
# =============================================================================

@router.get("/names", response_model=List[KnownName])
def list_known_names(
    session: Session = Depends(get_session)
):
    """List all known (named) faces for autocomplete suggestions.

    Returns unique names with the primary face for each (most embeddings).
    """
    # Get all known faces
    statement = select(Face).where(Face.is_known == True).order_by(col(Face.name))
    faces = session.exec(statement).all()

    # Group by name, keeping the one with most embeddings as primary
    name_to_face: Dict[str, Face] = {}
    for face in faces:
        if face.name not in name_to_face:
            name_to_face[face.name] = face
        elif face.embedding_count > name_to_face[face.name].embedding_count:
            name_to_face[face.name] = face

    return [
        KnownName(
            name=face.name,
            face_id=face.id,
            embedding_count=face.embedding_count,
            thumbnail_path=face.thumbnail_path
        )
        for face in name_to_face.values()
    ]


@router.post("/pretrain/scan")
def scan_pretrained_faces(background_tasks: BackgroundTasks):
    """Trigger a rescan of /data/faces/known for pretraining."""
    background_tasks.add_task(face_service.scan_known_faces)
    return {"status": "started"}


@router.get("/grouped", response_model=GroupedFacesResponse)
def get_grouped_faces(
    known_only: bool = False,
    session: Session = Depends(get_session)
):
    """Get faces grouped by name.

    Returns faces organized by their name, with aggregate stats.
    Useful for seeing all faces that share a name and merging them.
    """
    statement = select(Face)
    if known_only:
        statement = statement.where(Face.is_known == True)
    statement = statement.order_by(col(Face.name), col(Face.embedding_count).desc())

    faces = session.exec(statement).all()

    # Group faces by name
    groups_dict: Dict[str, List[Face]] = {}
    for face in faces:
        if face.name not in groups_dict:
            groups_dict[face.name] = []
        groups_dict[face.name].append(face)

    # Build response
    groups = []
    total_faces = 0

    for name, face_list in sorted(groups_dict.items()):
        # Primary face is the one with most embeddings
        primary = max(face_list, key=lambda f: f.embedding_count)

        total_embeddings = sum(f.embedding_count for f in face_list)
        first_seen = min(f.first_seen for f in face_list)
        last_seen = max(f.last_seen for f in face_list)
        is_known = any(f.is_known for f in face_list)

        members = [
            FaceGroupMember(
                id=f.id,
                thumbnail_path=f.thumbnail_path,
                first_seen=f.first_seen,
                last_seen=f.last_seen,
                embedding_count=f.embedding_count
            )
            for f in face_list
        ]

        groups.append(FaceGroup(
            name=name,
            is_known=is_known,
            face_count=len(face_list),
            total_embeddings=total_embeddings,
            first_seen=first_seen,
            last_seen=last_seen,
            primary_face_id=primary.id,
            primary_thumbnail=primary.thumbnail_path,
            faces=members
        ))

        total_faces += len(face_list)

    return GroupedFacesResponse(
        groups=groups,
        total_groups=len(groups),
        total_faces=total_faces
    )


@router.post("/merge", response_model=MergeFacesResponse)
def merge_faces(
    request: MergeFacesRequest,
    session: Session = Depends(get_session)
):
    """Merge multiple face records into a single identity.

    This combines all embeddings from the source faces into the target face,
    updates all events to point to the merged face, and deletes the source faces.

    The resulting face will have:
    - The specified target_name
    - All embeddings from all source faces (recomputed average)
    - All events from all source faces
    - The thumbnail from the face with most embeddings (or keep_face_id if specified)
    """
    if len(request.face_ids) < 1:
        raise HTTPException(status_code=400, detail="At least one face_id required")

    # Fetch all faces
    faces_to_merge = []
    for fid in request.face_ids:
        face = session.get(Face, fid)
        if not face:
            raise HTTPException(status_code=404, detail=f"Face {fid} not found")
        faces_to_merge.append(face)

    # Determine the primary face (to keep)
    if request.keep_face_id:
        primary = next((f for f in faces_to_merge if f.id == request.keep_face_id), None)
        if not primary:
            raise HTTPException(status_code=400, detail=f"keep_face_id {request.keep_face_id} not in face_ids")
    else:
        # Use face with most embeddings
        primary = max(faces_to_merge, key=lambda f: f.embedding_count)

    others = [f for f in faces_to_merge if f.id != primary.id]

    logger.info(f"Merging faces {[f.id for f in others]} into {primary.id} as '{request.target_name}'")

    # Collect all embeddings
    all_embeddings = []

    # Get embeddings from primary face
    primary_embeddings = session.exec(
        select(FaceEmbedding).where(FaceEmbedding.face_id == primary.id)
    ).all()
    for emb in primary_embeddings:
        try:
            all_embeddings.append(pickle.loads(emb.embedding))
        except Exception as e:
            logger.error(f"Failed to load embedding {emb.id}: {e}")

    # Also include the primary's original embedding if no FaceEmbedding records
    if not primary_embeddings and primary.embedding:
        try:
            all_embeddings.append(pickle.loads(primary.embedding))
        except Exception:
            pass

    # Merge embeddings from other faces
    for other in others:
        # Move FaceEmbedding records to primary
        other_embeddings = session.exec(
            select(FaceEmbedding).where(FaceEmbedding.face_id == other.id)
        ).all()

        for emb in other_embeddings:
            try:
                all_embeddings.append(pickle.loads(emb.embedding))
            except Exception as e:
                logger.error(f"Failed to load embedding {emb.id}: {e}")

            # Update to point to primary
            emb.face_id = primary.id
            session.add(emb)

        # Also include the other's original embedding if no FaceEmbedding records
        if not other_embeddings and other.embedding:
            try:
                emb_data = pickle.loads(other.embedding)
                all_embeddings.append(emb_data)
                # Create a FaceEmbedding record for it
                new_emb = FaceEmbedding(
                    face_id=primary.id,
                    embedding=other.embedding,
                    source="merge",
                    quality_score=0.0
                )
                session.add(new_emb)
            except Exception:
                pass

        # Update all events from other to point to primary
        events = session.exec(
            select(FaceEvent).where(FaceEvent.face_id == other.id)
        ).all()
        for event in events:
            event.face_id = primary.id
            event.face_name = request.target_name
            session.add(event)

        # Update primary's first_seen if other is older
        if other.first_seen < primary.first_seen:
            primary.first_seen = other.first_seen

        # Update primary's last_seen if other is newer
        if other.last_seen > primary.last_seen:
            primary.last_seen = other.last_seen

        # Delete the other face's thumbnail file
        if other.thumbnail_path and os.path.exists(other.thumbnail_path):
            try:
                os.remove(other.thumbnail_path)
            except Exception:
                pass

        # Delete the other face record
        session.delete(other)

    # Recompute average embedding for primary
    if all_embeddings:
        avg_embedding = np.mean(all_embeddings, axis=0)
        primary.avg_embedding = pickle.dumps(avg_embedding)
        primary.embedding_count = len(all_embeddings)
        # Update the primary embedding to the average as well
        primary.embedding = pickle.dumps(avg_embedding)

    # Update primary face
    primary.name = request.target_name
    primary.is_known = True
    session.add(primary)

    session.commit()
    session.refresh(primary)

    # Invalidate face service cache
    try:
        from app.services.detection.face_service import face_service
        face_service.last_cache_update = 0  # Force cache refresh
    except Exception:
        pass

    return MergeFacesResponse(
        merged_face_id=primary.id,
        merged_count=len(faces_to_merge),
        total_embeddings=primary.embedding_count,
        name=primary.name
    )


@router.post("/{face_id}/assign/{target_name}", response_model=MergeFacesResponse)
def assign_face_to_existing(
    face_id: int,
    target_name: str,
    session: Session = Depends(get_session)
):
    """Assign an unknown face to an existing known person.

    If target_name matches an existing known face, merges this face into that identity.
    Otherwise, just renames this face.
    """
    face = session.get(Face, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")

    # Find existing faces with this name
    existing = session.exec(
        select(Face).where(Face.name == target_name, Face.is_known == True)
    ).all()

    if existing:
        # Merge into the existing face with most embeddings
        primary_existing = max(existing, key=lambda f: f.embedding_count)

        # Include all existing faces plus the new one
        all_face_ids = [f.id for f in existing] + [face_id]

        # Use the merge endpoint logic
        merge_request = MergeFacesRequest(
            face_ids=all_face_ids,
            target_name=target_name,
            keep_face_id=primary_existing.id
        )
        return merge_faces(merge_request, session)
    else:
        # No existing face with this name - just rename
        face.name = target_name
        face.is_known = True
        session.add(face)
        session.commit()
        session.refresh(face)

        return MergeFacesResponse(
            merged_face_id=face.id,
            merged_count=1,
            total_embeddings=face.embedding_count,
            name=face.name
        )

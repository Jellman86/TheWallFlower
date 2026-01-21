"""API Router for transcription tuning."""

import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from sqlmodel import Session, select
from pydantic import BaseModel

from app.db import get_session
from app.models import TuningSample, TuningRun
from app.services.tuner_service import tuner_service, TUNING_DATA_DIR

router = APIRouter(prefix="/tuning", tags=["tuning"])

@router.post("/samples", response_model=TuningSample)
async def create_sample(
    file: UploadFile = File(...),
    ground_truth: Optional[str] = Form(None),
    stream_id: Optional[int] = Form(None),
    session: Session = Depends(get_session)
):
    """Upload a new audio sample for tuning."""
    filename = f"{uuid.uuid4()}.wav"
    filepath = os.path.join(TUNING_DATA_DIR, filename)
    
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    sample = TuningSample(
        filename=filename,
        ground_truth=ground_truth,
        stream_id=stream_id,
        original_transcript="" # Could run a default pass here
    )
    
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample

@router.get("/samples", response_model=List[TuningSample])
def list_samples(session: Session = Depends(get_session)):
    """List all tuning samples."""
    return session.exec(select(TuningSample).order_by(TuningSample.created_at.desc())).all()

class UpdateSampleRequest(BaseModel):
    ground_truth: Optional[str] = None
    stream_id: Optional[int] = None

@router.put("/samples/{sample_id}", response_model=TuningSample)
def update_sample(
    sample_id: int,
    request: UpdateSampleRequest,
    session: Session = Depends(get_session)
):
    """Update ground truth text for a sample."""
    sample = session.get(TuningSample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    if request.ground_truth is not None:
        sample.ground_truth = request.ground_truth
    if request.stream_id is not None:
        sample.stream_id = request.stream_id
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample

@router.post("/samples/{sample_id}/tune")
def run_tuning(
    sample_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Start a parameter sweep for a sample."""
    sample = session.get(TuningSample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    if not sample.ground_truth:
        raise HTTPException(status_code=400, detail="Ground truth required before tuning")

    background_tasks.add_task(tuner_service.run_sweep, sample_id)
    return {"status": "started", "sample_id": sample_id}


@router.post("/samples/{sample_id}/apply-best")
def apply_best_tuning(
    sample_id: int,
    session: Session = Depends(get_session)
):
    """Apply best tuning run to the sample's stream."""
    sample = session.get(TuningSample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    if not sample.stream_id:
        raise HTTPException(status_code=400, detail="Sample is not assigned to a stream")

    result = tuner_service.apply_best_to_stream(sample_id, sample.stream_id)
    if not result:
        raise HTTPException(status_code=404, detail="No tuning runs found")
    return {"status": "applied", "stream_id": sample.stream_id, "params": result}

@router.get("/samples/{sample_id}/runs", response_model=List[TuningRun])
def list_runs(
    sample_id: int,
    session: Session = Depends(get_session)
):
    """Get tuning results for a sample."""
    return session.exec(
        select(TuningRun)
        .where(TuningRun.sample_id == sample_id)
        .order_by(TuningRun.wer.asc())
    ).all()

@router.delete("/samples/{sample_id}")
def delete_sample(sample_id: int, session: Session = Depends(get_session)):
    """Delete a sample and its runs."""
    sample = session.get(TuningSample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    # Delete file
    filepath = os.path.join(TUNING_DATA_DIR, sample.filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass
        
    session.delete(sample)
    session.commit()
    return {"ok": True}

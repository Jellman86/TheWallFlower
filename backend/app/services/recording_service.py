import logging
from typing import List, Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.db import engine
from app.models import Recording

logger = logging.getLogger(__name__)

class RecordingService:
    def create_recording(self, recording: Recording) -> Optional[Recording]:
        try:
            with Session(engine) as session:
                session.add(recording)
                session.commit()
                session.refresh(recording)
                return recording
        except Exception as e:
            logger.error(f"Failed to create recording: {e}")
            return None

    def get_recordings(
        self, 
        stream_id: int, 
        start_time: Optional[datetime] = None, 
        end_time: Optional[datetime] = None
    ) -> List[Recording]:
        with Session(engine) as session:
            statement = select(Recording).where(Recording.stream_id == stream_id)
            if start_time:
                statement = statement.where(Recording.end_time >= start_time)
            if end_time:
                statement = statement.where(Recording.start_time <= end_time)
            
            statement = statement.order_by(Recording.start_time.asc())
            return session.exec(statement).all()

    def get_recording_by_path(self, file_path: str) -> Optional[Recording]:
        with Session(engine) as session:
            statement = select(Recording).where(Recording.file_path == file_path)
            return session.exec(statement).first()

    def delete_old_recordings(self, retention_days: int = 7):
        # This only cleans up DB entries for now. File deletion should be handled carefully.
        # Actually, the background task should iterate DB and delete files.
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        with Session(engine) as session:
            statement = select(Recording).where(
                Recording.end_time < cutoff,
                Recording.retention_locked == False
            )
            recordings = session.exec(statement).all()
            
            # TODO: Implement file deletion logic
            
            for rec in recordings:
                session.delete(rec)
            
            session.commit()
            if recordings:
                logger.info(f"Cleaned up {len(recordings)} old recording records")

recording_service = RecordingService()

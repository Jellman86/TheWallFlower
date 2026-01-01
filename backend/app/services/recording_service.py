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

    def delete_old_recordings(self):
        """Delete recordings older than retention policy."""
        from app.models import StreamConfig
        from pathlib import Path
        
        with Session(engine) as session:
            streams = session.exec(select(StreamConfig)).all()
            
            for stream in streams:
                if not stream.recording_retention_days:
                    continue
                    
                cutoff = datetime.utcnow() - timedelta(days=stream.recording_retention_days)
                
                # Find old recordings
                statement = select(Recording).where(
                    Recording.stream_id == stream.id,
                    Recording.end_time < cutoff,
                    Recording.retention_locked == False
                )
                recordings = session.exec(statement).all()
                
                deleted_count = 0
                for rec in recordings:
                    try:
                        # Delete file
                        full_path = Path("/data/recordings") / rec.file_path
                        if full_path.exists():
                            full_path.unlink()
                    except Exception as e:
                        logger.error(f"Failed to delete recording file {rec.file_path}: {e}")
                        # Continue to delete DB record anyway? 
                        # If we can't delete file, maybe we should keep DB record so we know it exists?
                        # But then we'll try to delete it forever.
                        # For now, delete DB record.
                    
                    session.delete(rec)
                    deleted_count += 1
                
                if deleted_count > 0:
                    logger.info(f"Stream {stream.id}: Cleaned up {deleted_count} old recordings")
            
            session.commit()

recording_service = RecordingService()

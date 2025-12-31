"""Transcript persistence service for TheWallflower."""

import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, select, col, func

from app.db import engine
from app.models import Transcript, TranscriptCreate

logger = logging.getLogger(__name__)


class TranscriptService:
    """Service for managing transcript persistence.
    
    Thread-safe implementation for handling transcripts from multiple stream workers.
    """

    def __init__(self):
        self._batch: List[TranscriptCreate] = []
        self._batch_size = 10  # Flush after this many transcripts
        self._last_flush = datetime.utcnow()
        self._flush_interval = timedelta(seconds=5)  # Flush at least every 5 seconds
        self._lock = threading.Lock()

    def add(self, transcript: TranscriptCreate) -> None:
        """Add a transcript to the batch for persistence.

        Transcripts are batched to reduce database writes.
        Call flush() to force immediate persistence.
        """
        should_flush = False
        
        with self._lock:
            self._batch.append(transcript)

            # Check flush conditions within lock
            if (len(self._batch) >= self._batch_size or
                datetime.utcnow() - self._last_flush > self._flush_interval):
                should_flush = True
        
        # Flush outside the add lock (flush acquires lock again)
        # Note: Optimization - flush() handles its own locking, but we could optimise
        # to hold lock throughout. However, DB write inside lock might block other adds.
        # Better to let add() be fast.
        if should_flush:
            self.flush()

    def flush(self) -> int:
        """Flush pending transcripts to database.

        Returns:
            Number of transcripts saved.
        """
        batch_to_save = []
        
        with self._lock:
            if not self._batch:
                return 0
            
            batch_to_save = self._batch
            self._batch = []
            self._last_flush = datetime.utcnow()

        if not batch_to_save:
            return 0

        try:
            with Session(engine) as session:
                for tc in batch_to_save:
                    transcript = Transcript(
                        stream_id=tc.stream_id,
                        text=tc.text,
                        start_time=tc.start_time,
                        end_time=tc.end_time,
                        is_final=tc.is_final,
                        confidence=tc.confidence,
                        speaker_id=tc.speaker_id,
                    )
                    session.add(transcript)
                session.commit()
                logger.debug(f"Flushed {len(batch_to_save)} transcripts to database")
                return len(batch_to_save)
        except Exception as e:
            logger.error(f"Failed to flush transcripts: {e}")
            # Put failed transcripts back in batch for retry
            with self._lock:
                self._batch = batch_to_save + self._batch
            return 0

    def get_by_stream(
        self,
        stream_id: int,
        limit: int = 50,
        offset: int = 0,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        final_only: bool = False,
    ) -> List[Transcript]:
        """Get transcripts for a stream.

        Args:
            stream_id: The stream ID to get transcripts for
            limit: Maximum number of transcripts to return
            offset: Number of transcripts to skip
            since: Only return transcripts after this time
            until: Only return transcripts before this time
            final_only: Only return final (not interim) transcripts

        Returns:
            List of transcripts, newest first
        """
        with Session(engine) as session:
            statement = select(Transcript).where(Transcript.stream_id == stream_id)

            if since:
                statement = statement.where(Transcript.created_at >= since)
            if until:
                statement = statement.where(Transcript.created_at <= until)
            if final_only:
                statement = statement.where(Transcript.is_final == True)

            statement = statement.order_by(col(Transcript.created_at).desc())
            statement = statement.offset(offset).limit(limit)

            return list(session.exec(statement).all())

    def search(
        self,
        query: str,
        stream_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Transcript]:
        """Search transcripts by text content.

        Args:
            query: Search query (case-insensitive substring match)
            stream_id: Optional stream ID to filter by
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of matching transcripts, newest first
        """
        with Session(engine) as session:
            statement = select(Transcript).where(
                col(Transcript.text).contains(query)
            )

            if stream_id is not None:
                statement = statement.where(Transcript.stream_id == stream_id)

            statement = statement.order_by(col(Transcript.created_at).desc())
            statement = statement.offset(offset).limit(limit)

            return list(session.exec(statement).all())

    def count_by_stream(self, stream_id: int) -> int:
        """Get total transcript count for a stream."""
        with Session(engine) as session:
            statement = select(func.count(Transcript.id)).where(
                Transcript.stream_id == stream_id
            )
            return session.exec(statement).one()

    def cleanup_old(
        self,
        max_age_days: int = 7,
        max_per_stream: int = 5000,
    ) -> int:
        """Clean up old transcripts.

        Args:
            max_age_days: Delete transcripts older than this many days
            max_per_stream: Keep only this many per stream

        Returns:
            Number of transcripts deleted
        """
        deleted = 0
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)

        try:
            with Session(engine) as session:
                # 1. Delete by age (Bulk delete is faster)
                from sqlmodel import delete
                statement = delete(Transcript).where(Transcript.created_at < cutoff)
                result = session.exec(statement)
                deleted += result.rowcount

                # 2. Enforce max per stream if needed
                if max_per_stream:
                    # Get list of stream IDs
                    streams_statement = select(Transcript.stream_id).distinct()
                    stream_ids = session.exec(streams_statement).all()
                    
                    for s_id in stream_ids:
                        # Find the count
                        count_statement = select(func.count(Transcript.id)).where(Transcript.stream_id == s_id)
                        total = session.exec(count_statement).one()
                        
                        if total > max_per_stream:
                            # Find the ID of the N-th newest transcript
                            nth_newest_statement = select(Transcript.id).where(
                                Transcript.stream_id == s_id
                            ).order_by(col(Transcript.created_at).desc()).offset(max_per_stream).limit(1)
                            
                            nth_id = session.exec(nth_newest_statement).first()
                            
                            if nth_id:
                                # Delete everything older than or equal to the N-th newest
                                delete_extra = delete(Transcript).where(
                                    Transcript.stream_id == s_id,
                                    Transcript.id <= nth_id
                                )
                                result = session.exec(delete_extra)
                                deleted += result.rowcount

                session.commit()
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} transcripts from database")

        return deleted

    def delete_by_stream(self, stream_id: int) -> int:
        """Delete all transcripts for a stream.

        Args:
            stream_id: The stream ID to delete transcripts for

        Returns:
            Number of transcripts deleted
        """
        with Session(engine) as session:
            transcripts = session.exec(
                select(Transcript).where(Transcript.stream_id == stream_id)
            ).all()

            count = len(transcripts)
            for t in transcripts:
                session.delete(t)

            session.commit()
            logger.info(f"Deleted {count} transcripts for stream {stream_id}")
            return count


# Global singleton instance
transcript_service = TranscriptService()
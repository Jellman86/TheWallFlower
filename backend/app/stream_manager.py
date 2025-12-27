"""Stream manager singleton for TheWallflower.

Manages the lifecycle of all stream workers, syncing with the database
and providing access to active streams.
"""

import atexit
import logging
import signal
import threading
from typing import Dict, List, Optional, Callable

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import StreamConfig
from app.worker import (
    StreamWorker, StreamStatus, TranscriptSegment,
    ConnectionState, CircuitBreakerState
)

logger = logging.getLogger(__name__)

# Health monitor configuration
HEALTH_CHECK_INTERVAL = 10  # seconds
FRAME_TIMEOUT_THRESHOLD = 30  # seconds without frame = stale


class StreamManager:
    """Singleton manager for all stream workers.

    Responsible for:
    - Starting/stopping workers based on database state
    - Providing access to active workers for streaming endpoints
    - Broadcasting transcript updates to connected clients
    """

    _instance: Optional["StreamManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "StreamManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._workers: Dict[int, StreamWorker] = {}
        self._workers_lock = threading.Lock()
        self._shutting_down = False

        # WhisperLive configuration from settings
        self._whisper_host = settings.whisper_host
        self._whisper_port = settings.whisper_port

        # Callback for transcript updates (for SSE/WebSocket broadcasting)
        self._transcript_callbacks: List[Callable[[int, TranscriptSegment], None]] = []

        # Health monitor thread
        self._health_thread: Optional[threading.Thread] = None
        self._health_check_interval = HEALTH_CHECK_INTERVAL

        # Register shutdown handlers
        atexit.register(self._atexit_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self._initialized = True
        logger.info(
            f"StreamManager initialized (Whisper: {self._whisper_host}:{self._whisper_port})"
        )

    def register_transcript_callback(
        self, callback: Callable[[int, TranscriptSegment], None]
    ) -> None:
        """Register a callback to receive transcript updates."""
        self._transcript_callbacks.append(callback)

    def unregister_transcript_callback(
        self, callback: Callable[[int, TranscriptSegment], None]
    ) -> None:
        """Unregister a transcript callback."""
        if callback in self._transcript_callbacks:
            self._transcript_callbacks.remove(callback)

    def _on_transcript(self, stream_id: int, segment: TranscriptSegment) -> None:
        """Internal callback when a transcript is received."""
        for callback in self._transcript_callbacks:
            try:
                callback(stream_id, segment)
            except Exception as e:
                logger.error(f"Transcript callback error: {e}")

    def start_stream(self, stream_id: int) -> bool:
        """Start a stream worker for the given stream ID.

        Args:
            stream_id: Database ID of the stream to start

        Returns:
            True if started successfully, False otherwise
        """
        with self._workers_lock:
            # Check if already running
            if stream_id in self._workers:
                logger.warning(f"Stream {stream_id} already running")
                return True

            # Get stream config from database
            with Session(engine) as session:
                config = session.get(StreamConfig, stream_id)
                if not config:
                    logger.error(f"Stream {stream_id} not found in database")
                    return False

                # Create and start worker
                worker = StreamWorker(
                    config=config,
                    whisper_host=self._whisper_host,
                    whisper_port=self._whisper_port,
                    on_transcript=self._on_transcript
                )

            try:
                worker.start()
                self._workers[stream_id] = worker
                logger.info(f"Started stream {stream_id}: {config.name}")
                return True
            except Exception as e:
                logger.error(f"Failed to start stream {stream_id}: {e}")
                return False

    def stop_stream(self, stream_id: int) -> bool:
        """Stop a stream worker.

        Args:
            stream_id: Database ID of the stream to stop

        Returns:
            True if stopped successfully, False if not running
        """
        with self._workers_lock:
            worker = self._workers.pop(stream_id, None)
            if worker:
                worker.stop()
                logger.info(f"Stopped stream {stream_id}")
                return True
            return False

    def restart_stream(self, stream_id: int) -> bool:
        """Restart a stream worker (stop then start)."""
        self.stop_stream(stream_id)
        return self.start_stream(stream_id)

    def get_worker(self, stream_id: int) -> Optional[StreamWorker]:
        """Get a stream worker by ID."""
        with self._workers_lock:
            return self._workers.get(stream_id)

    def get_all_workers(self) -> Dict[int, StreamWorker]:
        """Get all active workers."""
        with self._workers_lock:
            return dict(self._workers)

    def get_status(self, stream_id: int) -> Optional[StreamStatus]:
        """Get the status of a specific stream."""
        worker = self.get_worker(stream_id)
        if worker:
            return worker.status
        return None

    def get_all_statuses(self) -> Dict[int, StreamStatus]:
        """Get status of all active streams."""
        with self._workers_lock:
            return {
                stream_id: worker.status
                for stream_id, worker in self._workers.items()
            }

    def reload_all(self) -> None:
        """Sync running workers with database state.

        - Starts workers for streams in DB that aren't running
        - Stops workers for streams that were deleted from DB
        """
        logger.info("Reloading all streams from database")

        with Session(engine) as session:
            # Get all stream IDs from database
            statement = select(StreamConfig.id)
            db_stream_ids = set(session.exec(statement).all())

        with self._workers_lock:
            running_stream_ids = set(self._workers.keys())

        # Stop workers for deleted streams
        for stream_id in running_stream_ids - db_stream_ids:
            logger.info(f"Stopping removed stream {stream_id}")
            self.stop_stream(stream_id)

        # Start workers for new streams
        for stream_id in db_stream_ids - running_stream_ids:
            logger.info(f"Starting new stream {stream_id}")
            self.start_stream(stream_id)

    def start_all(self) -> None:
        """Start workers for all streams in the database."""
        logger.info("Starting all streams")

        with Session(engine) as session:
            statement = select(StreamConfig)
            streams = session.exec(statement).all()

        for stream in streams:
            self.start_stream(stream.id)

        # Start health monitor
        self._start_health_monitor()

    def stop_all(self) -> None:
        """Stop all running workers."""
        logger.info("Stopping all streams")

        with self._workers_lock:
            stream_ids = list(self._workers.keys())

        for stream_id in stream_ids:
            self.stop_stream(stream_id)

    def force_retry(self, stream_id: int) -> bool:
        """Force a stream to retry connection immediately, resetting circuit breaker.

        Args:
            stream_id: Database ID of the stream

        Returns:
            True if reset successfully, False if stream not running
        """
        with self._workers_lock:
            worker = self._workers.get(stream_id)
            if not worker:
                return False

            # Reset circuit breaker to half-open (will attempt reconnection)
            worker._status.circuit_breaker_state = CircuitBreakerState.HALF_OPEN
            worker._status.consecutive_failures = 0
            worker._status.retry_count = 0
            worker._status.next_retry_time = None
            worker._status.error = "Retry requested - reconnecting..."
            worker._emit_status_event()

            logger.info(f"Stream {stream_id}: Force retry requested, circuit breaker reset")
            return True

    def _start_health_monitor(self) -> None:
        """Start the health monitoring thread."""
        if self._health_thread and self._health_thread.is_alive():
            return

        self._health_thread = threading.Thread(
            target=self._health_monitor_loop,
            name="stream-health-monitor",
            daemon=True
        )
        self._health_thread.start()
        logger.info("Health monitor started")

    def _health_monitor_loop(self) -> None:
        """Monitor thread health and resurrect dead threads."""
        import time
        from datetime import datetime

        while not self._shutting_down:
            try:
                self._check_thread_health()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

            time.sleep(self._health_check_interval)

    def _check_thread_health(self) -> None:
        """Check all workers and resurrect dead threads."""
        from datetime import datetime

        with self._workers_lock:
            for stream_id, worker in list(self._workers.items()):
                status = worker.status

                # Skip if not supposed to be running
                if not status.is_running:
                    continue

                # Check if video thread died unexpectedly
                if not status.video_thread_alive:
                    logger.warning(f"Stream {stream_id}: Video thread dead, resurrecting")
                    self._resurrect_video_thread(worker)

                # Check if audio thread died unexpectedly (when whisper is enabled)
                if (worker.config.whisper_enabled and
                    not status.audio_thread_alive):
                    logger.warning(f"Stream {stream_id}: Audio thread dead, resurrecting")
                    self._resurrect_audio_thread(worker)

                # Check for stale streams (no frames for too long)
                if status.video_connected and status.last_frame_time:
                    time_since_frame = (datetime.now() - status.last_frame_time).total_seconds()
                    if time_since_frame > FRAME_TIMEOUT_THRESHOLD:
                        logger.warning(f"Stream {stream_id}: No frames for {int(time_since_frame)}s, marking stale")
                        worker._status.video_connected = False
                        worker._status.error = f"Stream stale - no frames for {int(time_since_frame)}s"
                        worker._status.connection_state = ConnectionState.RETRYING
                        worker._emit_status_event()

    def _resurrect_video_thread(self, worker: StreamWorker) -> None:
        """Resurrect a dead video thread."""
        try:
            worker._video_thread = threading.Thread(
                target=worker._video_loop,
                name=f"video-{worker.config.id}",
                daemon=True
            )
            worker._video_thread.start()
            logger.info(f"Stream {worker.config.id}: Video thread resurrected")
        except Exception as e:
            logger.error(f"Stream {worker.config.id}: Failed to resurrect video thread: {e}")

    def _resurrect_audio_thread(self, worker: StreamWorker) -> None:
        """Resurrect a dead audio thread."""
        try:
            worker._audio_thread = threading.Thread(
                target=worker._audio_loop,
                name=f"audio-{worker.config.id}",
                daemon=True
            )
            worker._audio_thread.start()
            logger.info(f"Stream {worker.config.id}: Audio thread resurrected")
        except Exception as e:
            logger.error(f"Stream {worker.config.id}: Failed to resurrect audio thread: {e}")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        if self._shutting_down:
            logger.warning("Forced shutdown requested")
            return

        self._shutting_down = True
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.stop_all()

    def _atexit_handler(self) -> None:
        """Handle process exit - ensure all workers are stopped."""
        if not self._shutting_down:
            logger.info("Process exiting, cleaning up workers...")
            self.stop_all()

    @property
    def is_shutting_down(self) -> bool:
        """Check if the manager is shutting down."""
        return self._shutting_down


# Global singleton instance
stream_manager = StreamManager()

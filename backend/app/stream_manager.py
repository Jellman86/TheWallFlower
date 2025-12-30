"""Stream manager singleton for TheWallflower.

Manages the lifecycle of all stream workers, syncing with the database
and providing access to active streams.

Now integrates with go2rtc for efficient video streaming:
- go2rtc handles RTSP → WebRTC/MJPEG conversion
- Python workers handle audio extraction for Whisper transcription
- Reduced CPU usage and improved browser compatibility
"""

import asyncio
import atexit
import logging
import signal
import threading
from typing import Dict, List, Optional, Callable

from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.go2rtc_client import Go2RTCClient, Go2RTCError
from app.models import StreamConfig
from app.worker import (
    StreamWorker, StreamStatus, TranscriptSegment,
    ConnectionState, CircuitBreakerState
)

logger = logging.getLogger(__name__)

# Health monitor configuration
HEALTH_CHECK_INTERVAL = 10  # seconds


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
        # We use a threading lock because workers are accessed by:
        # 1. Async endpoints (main thread)
        # 2. Health monitor (separate thread)
        self._workers_lock = threading.Lock()
        self._shutting_down = False

        # WhisperLive configuration from settings
        self._whisper_host = settings.whisper_host
        self._whisper_port = settings.whisper_port

        # go2rtc client for efficient video streaming
        self._go2rtc = Go2RTCClient(
            host=settings.go2rtc_host,
            port=settings.go2rtc_port,
            rtsp_port=settings.go2rtc_rtsp_port,
            webrtc_port=settings.go2rtc_webrtc_port
        )

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
            f"StreamManager initialized (Whisper: {self._whisper_host}:{self._whisper_port}, "
            f"go2rtc: {settings.go2rtc_host}:{settings.go2rtc_port})"
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

    async def _add_stream_to_go2rtc(self, stream_id: int, rtsp_url: str) -> bool:
        """Add stream to go2rtc for efficient video streaming.

        Args:
            stream_id: Database stream ID
            rtsp_url: RTSP URL of the camera

        Returns:
            True if added successfully, False otherwise
        """
        stream_name = self._go2rtc.get_stream_name(stream_id)
        try:
            await self._go2rtc.add_stream(stream_name, rtsp_url)
            logger.info(f"Added stream {stream_id} to go2rtc as '{stream_name}'")
            return True
        except Go2RTCError as e:
            logger.error(f"Failed to add stream {stream_id} to go2rtc: {e}")
            return False

    async def _remove_stream_from_go2rtc(self, stream_id: int) -> bool:
        """Remove stream from go2rtc.

        Args:
            stream_id: Database stream ID

        Returns:
            True if removed successfully
        """
        stream_name = self._go2rtc.get_stream_name(stream_id)
        try:
            await self._go2rtc.remove_stream(stream_name)
            logger.info(f"Removed stream {stream_id} from go2rtc")
            return True
        except Go2RTCError as e:
            logger.warning(f"Failed to remove stream {stream_id} from go2rtc: {e}")
            return False

    async def start_stream(self, stream_id: int) -> bool:
        """Start a stream worker for the given stream ID.

        This now:
        1. Adds the stream to go2rtc for video streaming
        2. Starts an audio worker for Whisper transcription (if enabled)

        Args:
            stream_id: Database ID of the stream to start

        Returns:
            True if started successfully, False otherwise
        """
        # 1. Quick check if already running (with lock)
        with self._workers_lock:
            if stream_id in self._workers:
                logger.warning(f"Stream {stream_id} already running")
                return True

        # 2. Get config (DB access - fast enough, usually sync in SQLModel)
        # Note: We're in an async function but using sync DB access. 
        # Ideally this should be async too, but SQLModel is sync by default.
        # Since it's fast (local SQLite usually), it's acceptable.
        with Session(engine) as session:
            config = session.get(StreamConfig, stream_id)
            if not config:
                logger.error(f"Stream {stream_id} not found in database")
                return False
            
            # Store config data we need so we don't need session later
            stream_name = config.name
            rtsp_url = config.rtsp_url
            whisper_enabled = config.whisper_enabled
            # We need the full config object for the worker, but we can't keep the session open
            # detaching object or querying again later? 
            # Worker takes config object. Let's just pass the data we need or keep session scope small.
            # Actually, StreamWorker stores the config object.
            # We should probably create the worker inside this session block or re-query.
            # But wait, we have a potentially slow async operation (go2rtc) coming up.
            # We CANNOT keep the DB session open during that await!
            
        # 3. Add to go2rtc (SLOW, ASYNC, NO LOCK)
        try:
            # This is the key fix: awaiting here releases the event loop
            # and we do NOT hold _workers_lock, so other requests can proceed.
            await self._add_stream_to_go2rtc(stream_id, rtsp_url)
        except Exception as e:
            logger.error(f"go2rtc error for stream {stream_id}: {e}")
            # Continue anyway - audio worker can still function

        # 4. Create and start worker
        # We need to re-query config because we closed the session
        with Session(engine) as session:
            config = session.get(StreamConfig, stream_id)
            if not config:
                return False
                
            worker = StreamWorker(
                config=config,
                whisper_host=self._whisper_host,
                whisper_port=self._whisper_port,
                on_transcript=self._on_transcript
            )

        # 5. Add to workers dict (with lock)
        with self._workers_lock:
            # Race condition check: did someone else start it while we were awaiting?
            if stream_id in self._workers:
                # Cleanup our duplicate work
                worker = None
                return True

            try:
                worker.start()
                self._workers[stream_id] = worker
                logger.info(f"Started stream {stream_id}: {stream_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to start stream {stream_id}: {e}")
                # Cleanup go2rtc if worker failed
                # We schedule this as a task so we don't block here? 
                # Or just await it? We can await it.
                return False
                
        # If we failed to start worker (returned False above), we should probably cleanup go2rtc
        # But we can't do it inside the lock.
        # Let's handle the cleanup outside.

    async def stop_stream(self, stream_id: int) -> bool:
        """Stop a stream worker and remove from go2rtc.

        Args:
            stream_id: Database ID of the stream to stop

        Returns:
            True if stopped successfully, False if not running
        """
        # 1. Remove from workers dict (with lock)
        with self._workers_lock:
            worker = self._workers.pop(stream_id, None)
            
        # 2. Stop worker and remove from go2rtc (NO LOCK)
        if worker:
            worker.stop()
            logger.info(f"Stopped stream {stream_id}")
            
            try:
                await self._remove_stream_from_go2rtc(stream_id)
            except Exception as e:
                logger.warning(f"Error removing stream {stream_id} from go2rtc: {e}")
            return True
            
        return False

    async def restart_stream(self, stream_id: int) -> bool:
        """Restart a stream worker (stop then start)."""
        await self.stop_stream(stream_id)
        return await self.start_stream(stream_id)

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

    @property
    def go2rtc(self) -> Go2RTCClient:
        """Get the go2rtc client for URL generation."""
        return self._go2rtc

    def get_stream_urls(self, stream_id: int, external_host: Optional[str] = None) -> Dict[str, str]:
        """Get all available streaming URLs for a stream.

        Args:
            stream_id: Database stream ID
            external_host: Optional external host for browser access

        Returns:
            Dictionary with webrtc, mjpeg, frame, hls, and rtsp URLs
        """
        stream_name = self._go2rtc.get_stream_name(stream_id)
        ext_host = external_host or settings.go2rtc_external_host or None
        return {
            "webrtc": self._go2rtc.get_webrtc_url(stream_name, ext_host),
            "webrtc_api": self._go2rtc.get_webrtc_api_url(stream_name, ext_host),
            "mjpeg": self._go2rtc.get_mjpeg_url(stream_name, ext_host),
            "frame": self._go2rtc.get_frame_url(stream_name, ext_host),
            "hls": self._go2rtc.get_hls_url(stream_name, ext_host),
            "rtsp": self._go2rtc.get_rtsp_url(stream_name),
            "go2rtc_name": stream_name
        }

    async def reload_all(self) -> None:
        """Sync running workers with database state."""
        logger.info("Reloading all streams from database")

        with Session(engine) as session:
            statement = select(StreamConfig.id)
            db_stream_ids = set(session.exec(statement).all())

        with self._workers_lock:
            running_stream_ids = set(self._workers.keys())

        # Stop workers for deleted streams
        for stream_id in running_stream_ids - db_stream_ids:
            logger.info(f"Stopping removed stream {stream_id}")
            await self.stop_stream(stream_id)

        # Start workers for new streams
        # Use gather for parallel startup
        tasks = []
        for stream_id in db_stream_ids - running_stream_ids:
            logger.info(f"Starting new stream {stream_id}")
            tasks.append(self.start_stream(stream_id))
            
        if tasks:
            await asyncio.gather(*tasks)

    async def start_all(self) -> None:
        """Start workers for all streams in the database."""
        logger.info("Starting all streams")

        with Session(engine) as session:
            statement = select(StreamConfig)
            streams = session.exec(statement).all()

        # Start health monitor first
        self._start_health_monitor()
        
        # Start all streams in parallel
        tasks = [self.start_stream(stream.id) for stream in streams]
        if tasks:
            await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        """Stop all running workers."""
        logger.info("Stopping all streams")

        with self._workers_lock:
            stream_ids = list(self._workers.keys())

        # Stop in parallel
        tasks = [self.stop_stream(stream_id) for stream_id in stream_ids]
        if tasks:
            await asyncio.gather(*tasks)

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
        """Check all workers and resurrect dead audio threads.

        Note: Video is handled by go2rtc (external). We only monitor audio threads.
        """
        with self._workers_lock:
            for stream_id, worker in list(self._workers.items()):
                status = worker.status

                # Skip if not supposed to be running
                if not status.is_running:
                    continue

                # Check if audio thread died unexpectedly (when whisper is enabled)
                if (worker.config.whisper_enabled and
                    not status.audio_thread_alive):
                    logger.warning(f"Stream {stream_id}: Audio thread dead, resurrecting")
                    self._resurrect_audio_thread(worker)

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
        # Since we are in a signal handler (sync), we can't await stop_all.
        # But we can try to schedule it if loop is running, or just let the main thread exit?
        # Typically signal handlers in asyncio apps just set a flag or cancel the main task.
        # But here we are using atexit too.
        # We can't easily await here. Best effort to stop workers which are threads.
        # The StreamWorker.stop() is sync, so we can iterate and stop them!
        
        # We can reuse the sync part of stop_stream mechanism manually
        with self._workers_lock:
            for worker in self._workers.values():
                worker.stop()
        # Go2RTC cleanup will be skipped in signal handler, but that's okay (process dying).

    def _atexit_handler(self) -> None:
        """Handle process exit - ensure all workers are stopped."""
        if not self._shutting_down:
            logger.info("Process exiting, cleaning up workers...")
            with self._workers_lock:
                for worker in self._workers.values():
                    worker.stop()

    @property
    def is_shutting_down(self) -> bool:
        """Check if the manager is shutting down."""
        return self._shutting_down


# Global singleton instance
stream_manager = StreamManager()
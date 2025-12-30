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
from datetime import datetime, timedelta

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
WATCHDOG_TIMEOUT = 30 # seconds - max time without audio before restart


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

        self._whisper_host = settings.whisper_host
        self._whisper_port = settings.whisper_port

        self._go2rtc = Go2RTCClient(
            host=settings.go2rtc_host,
            port=settings.go2rtc_port,
            rtsp_port=settings.go2rtc_rtsp_port,
            webrtc_port=settings.go2rtc_webrtc_port
        )

        self._transcript_callbacks: List[Callable[[int, TranscriptSegment], None]] = []
        self._health_thread: Optional[threading.Thread] = None
        self._health_check_interval = HEALTH_CHECK_INTERVAL

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
        self._transcript_callbacks.append(callback)

    def unregister_transcript_callback(
        self, callback: Callable[[int, TranscriptSegment], None]
    ) -> None:
        if callback in self._transcript_callbacks:
            self._transcript_callbacks.remove(callback)

    def _on_transcript(self, stream_id: int, segment: TranscriptSegment) -> None:
        for callback in self._transcript_callbacks:
            try:
                callback(stream_id, segment)
            except Exception as e:
                logger.error(f"Transcript callback error: {e}")

    async def _add_stream_to_go2rtc(self, stream_id: int, rtsp_url: str) -> bool:
        stream_name = self._go2rtc.get_stream_name(stream_id)
        try:
            await self._go2rtc.add_stream(stream_name, rtsp_url)
            logger.info(f"Added stream {stream_id} to go2rtc as '{stream_name}'")
            return True
        except Go2RTCError as e:
            logger.error(f"Failed to add stream {stream_id} to go2rtc: {e}")
            return False

    async def _remove_stream_from_go2rtc(self, stream_id: int) -> bool:
        stream_name = self._go2rtc.get_stream_name(stream_id)
        try:
            await self._go2rtc.remove_stream(stream_name)
            logger.info(f"Removed stream {stream_id} from go2rtc")
            return True
        except Go2RTCError as e:
            logger.warning(f"Failed to remove stream {stream_id} from go2rtc: {e}")
            return False

    async def start_stream(self, stream_id: int) -> bool:
        with self._workers_lock:
            if stream_id in self._workers:
                logger.warning(f"Stream {stream_id} already running")
                return True

        with Session(engine) as session:
            config = session.get(StreamConfig, stream_id)
            if not config:
                logger.error(f"Stream {stream_id} not found in database")
                return False
            
            stream_name = config.name
            rtsp_url = config.rtsp_url
            
        try:
            await self._add_stream_to_go2rtc(stream_id, rtsp_url)
        except Exception as e:
            logger.error(f"go2rtc error for stream {stream_id}: {e}")

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

        with self._workers_lock:
            if stream_id in self._workers:
                worker = None
                return True

            try:
                worker.start()
                self._workers[stream_id] = worker
                logger.info(f"Started stream {stream_id}: {stream_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to start stream {stream_id}: {e}")
                return False
                

    async def stop_stream(self, stream_id: int) -> bool:
        with self._workers_lock:
            worker = self._workers.pop(stream_id, None)
            
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
        await self.stop_stream(stream_id)
        return await self.start_stream(stream_id)

    def get_worker(self, stream_id: int) -> Optional[StreamWorker]:
        with self._workers_lock:
            return self._workers.get(stream_id)

    def get_all_workers(self) -> Dict[int, StreamWorker]:
        with self._workers_lock:
            return dict(self._workers)

    def get_status(self, stream_id: int) -> Optional[StreamStatus]:
        worker = self.get_worker(stream_id)
        if worker:
            return worker.status
        return None

    def get_all_statuses(self) -> Dict[int, StreamStatus]:
        with self._workers_lock:
            return {
                stream_id: worker.status
                for stream_id, worker in self._workers.items()
            }

    @property
    def go2rtc(self) -> Go2RTCClient:
        return self._go2rtc

    def get_stream_urls(self, stream_id: int, external_host: Optional[str] = None) -> Dict[str, str]:
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
        logger.info("Reloading all streams from database")

        with Session(engine) as session:
            statement = select(StreamConfig.id)
            db_stream_ids = set(session.exec(statement).all())

        with self._workers_lock:
            running_stream_ids = set(self._workers.keys())

        for stream_id in running_stream_ids - db_stream_ids:
            logger.info(f"Stopping removed stream {stream_id}")
            await self.stop_stream(stream_id)

        tasks = []
        for stream_id in db_stream_ids - running_stream_ids:
            logger.info(f"Starting new stream {stream_id}")
            tasks.append(self.start_stream(stream_id))
            
        if tasks:
            await asyncio.gather(*tasks)

    async def start_all(self) -> None:
        logger.info("Starting all streams")

        with Session(engine) as session:
            statement = select(StreamConfig)
            streams = session.exec(statement).all()

        self._start_health_monitor()
        
        tasks = [self.start_stream(stream.id) for stream in streams]
        if tasks:
            await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        logger.info("Stopping all streams")

        with self._workers_lock:
            stream_ids = list(self._workers.keys())

        tasks = [self.stop_stream(stream_id) for stream_id in stream_ids]
        if tasks:
            await asyncio.gather(*tasks)

    def force_retry(self, stream_id: int) -> bool:
        with self._workers_lock:
            worker = self._workers.get(stream_id)
            if not worker:
                return False

            # Reset circuit breaker
            worker._status.circuit_breaker_state = CircuitBreakerState.HALF_OPEN
            worker._status.consecutive_failures = 0
            worker._status.retry_count = 0
            worker._status.next_retry_time = None
            worker._status.error = "Retry requested - reconnecting..."
            worker._emit_status_event()

            logger.info(f"Stream {stream_id}: Force retry requested, circuit breaker reset")
            return True

    def _start_health_monitor(self) -> None:
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
        import time

        while not self._shutting_down:
            try:
                self._check_thread_health()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

            time.sleep(self._health_check_interval)

    def _check_thread_health(self) -> None:
        """Check worker health and restart stuck threads."""
        now = datetime.now()
        
        with self._workers_lock:
            workers_to_check = list(self._workers.items())

        for stream_id, worker in workers_to_check:
            status = worker.status

            if not status.is_running:
                continue

            # 1. Check if audio thread died unexpectedly
            if (worker.config.whisper_enabled and not status.audio_thread_alive):
                logger.warning(f"Stream {stream_id}: Audio thread dead, resurrecting")
                self._resurrect_audio_thread(worker)
                continue

            # 2. WATCHDOG: Check if audio is flowing
            if worker.config.whisper_enabled and status.audio_thread_alive:
                last_activity = status.last_audio_time or datetime.fromtimestamp(0)
                # If no audio for WATCHDOG_TIMEOUT seconds, assume hung thread
                if (now - last_activity).total_seconds() > WATCHDOG_TIMEOUT:
                     logger.warning(f"Stream {stream_id}: Watchdog timeout! Audio stuck since {last_activity}. Restarting worker.")
                     # We can't use async restart_stream here (we are in a sync thread).
                     # We must manually stop and start the worker thread.
                     # But we must be careful about locks.
                     
                     # NOTE: worker.stop() joins the thread. If the thread is truly hung (blocked on read),
                     # the join will timeout (5s) and we force kill FFmpeg. This releases the read.
                     try:
                         worker.stop()
                         worker.start()
                         logger.info(f"Stream {stream_id}: Worker restarted successfully by watchdog.")
                     except Exception as e:
                         logger.error(f"Stream {stream_id}: Failed to watchdog-restart: {e}")


    def _resurrect_audio_thread(self, worker: StreamWorker) -> None:
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
        if self._shutting_down:
            logger.warning("Forced shutdown requested")
            return

        self._shutting_down = True
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        
        with self._workers_lock:
            for worker in self._workers.values():
                worker.stop()

    def _atexit_handler(self) -> None:
        if not self._shutting_down:
            logger.info("Process exiting, cleaning up workers...")
            with self._workers_lock:
                for worker in self._workers.values():
                    worker.stop()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down


# Global singleton instance
stream_manager = StreamManager()

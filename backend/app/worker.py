"""Stream worker for TheWallflower.

Handles audio extraction from RTSP streams for WhisperLive transcription.

With go2rtc integration:
- go2rtc handles ALL video streaming (RTSP → WebRTC/MJPEG)
- This worker ONLY handles audio extraction for Whisper transcription
- Audio is extracted from go2rtc's RTSP restream (localhost:8955)
- No OpenCV video processing - eliminates CPU overhead and browser hangs
"""

import asyncio
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Callable
import json

import websockets

from app.models import StreamConfig, TranscriptCreate
from app.services.transcript_service import transcript_service
from app.services.event_broadcaster import event_broadcaster

logger = logging.getLogger(__name__)

# Reconnection backoff configuration
WHISPER_RECONNECT_BACKOFF = [1, 2, 5, 10, 30, 60]  # seconds
FFMPEG_RESTART_DELAY = 2  # seconds
THREAD_HEALTH_CHECK_INTERVAL = 10  # seconds


class ConnectionState(str, Enum):
    """Stream connection states (for audio/whisper)."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RETRYING = "retrying"
    FAILED = "failed"
    STOPPED = "stopped"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states for connection management."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests after failures
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class TranscriptSegment:
    """A segment of transcribed text."""
    text: str
    start_time: float
    end_time: float
    is_final: bool = False


@dataclass
class StreamStatus:
    """Current status of a stream worker.

    Note: Video is handled by go2rtc (external). This tracks audio/Whisper status.
    video_connected is always True when running (go2rtc handles video).
    """
    stream_id: int
    is_running: bool = False
    video_connected: bool = False  # Always True when running (go2rtc handles it)
    audio_connected: bool = False
    whisper_connected: bool = False
    fps: float = 0.0  # Placeholder - actual FPS from go2rtc
    error: Optional[str] = None
    last_transcript: Optional[str] = None
    # Health tracking (audio thread only now)
    video_thread_alive: bool = False  # Deprecated - kept for API compatibility
    audio_thread_alive: bool = False
    ffmpeg_restarts: int = 0
    whisper_reconnects: int = 0
    last_frame_time: Optional[datetime] = None  # Deprecated - kept for API compatibility
    last_audio_time: Optional[datetime] = None
    # Connection tracking for audio/Whisper
    connection_state: ConnectionState = ConnectionState.STOPPED
    retry_count: int = 0
    next_retry_time: Optional[datetime] = None
    last_successful_connection: Optional[datetime] = None
    # Circuit breaker for connection management
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    consecutive_failures: int = 0


class StreamWorker:
    """Worker that handles audio extraction for WhisperLive transcription.

    Video streaming is handled by go2rtc (external process).
    This worker only manages:
    - Audio thread: Extracts audio via FFmpeg from go2rtc restream, sends to WhisperLive
    """

    def __init__(
        self,
        config: StreamConfig,
        whisper_host: str = "localhost",
        whisper_port: int = 9090,
        on_transcript: Optional[Callable[[int, TranscriptSegment], None]] = None,
    ):
        self.config = config
        self.whisper_host = whisper_host
        self.whisper_port = whisper_port
        self.on_transcript = on_transcript

        # Thread control
        self._stop_event = threading.Event()
        self._audio_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None
        
        # Lock for thread-safe status updates
        self._status_lock = threading.Lock()

        # Status
        self._status = StreamStatus(stream_id=config.id)

        # Transcript buffer and deduplication
        self._transcript_segments: List[TranscriptSegment] = []
        self._transcript_lock = threading.Lock()
        self._processed_segment_ids = set() # Track (start_time, text) for is_final segments

        # Reconnection tracking
        self._whisper_reconnect_attempts = 0
    
    def _cleanup_ffmpeg(self, process: subprocess.Popen, timeout: int = 5):
        """Clean up FFmpeg process robustly."""
        if process is None:
            return
        try:
            # Close pipes first to unblock any reads
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
            
            # Terminate gracefully
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't shut down
                logger.warning(f"Force killing FFmpeg for stream {self.config.id}")
                process.kill()
                process.wait(timeout=2)
        except Exception as e:
            logger.error(f"FFmpeg cleanup error: {e}")

    def _update_status(self, **kwargs):
        """Thread-safe status update helper."""
        with self._status_lock:
            for key, value in kwargs.items():
                setattr(self._status, key, value)

    def _emit_status_event(self) -> None:
        """Emit current status via SSE."""
        status = self.status # Access via property to ensure lock usage
        event_broadcaster.emit_status(self.config.id, {
            "is_running": status.is_running,
            "video_connected": status.video_connected,
            "audio_connected": status.audio_connected,
            "whisper_connected": status.whisper_connected,
            "fps": status.fps,
            "error": status.error,
            "video_thread_alive": status.video_thread_alive,
            "audio_thread_alive": status.audio_thread_alive,
            "ffmpeg_restarts": status.ffmpeg_restarts,
            "whisper_reconnects": status.whisper_reconnects,
            "connection_state": status.connection_state.value,
            "retry_count": status.retry_count,
            "next_retry_time": status.next_retry_time.isoformat() if status.next_retry_time else None,
        })

    @property
    def status(self) -> StreamStatus:
        """Get current stream status with thread health."""
        with self._status_lock:
            import copy
            self._status.video_thread_alive = self._status.is_running
            self._status.audio_thread_alive = (
                self._audio_thread is not None and self._audio_thread.is_alive()
            )
            return copy.copy(self._status)

    @property
    def transcripts(self) -> List[TranscriptSegment]:
        """Get all transcript segments."""
        with self._transcript_lock:
            return list(self._transcript_segments)

    def _write_transcript_to_file(self, segment: TranscriptSegment) -> None:
        """Write a transcript segment to file."""
        import os
        from datetime import datetime

        try:
            if getattr(self.config, 'transcript_file_path', None):
                file_path = self.config.transcript_file_path
            else:
                safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.config.name)
                file_path = f"/data/transcripts/{safe_name}.txt"

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {segment.text}\n")

        except Exception as e:
            logger.error(f"Failed to write transcript to file: {e}")

    def start(self) -> None:
        """Start the stream worker."""
        with self._status_lock:
            if self._status.is_running:
                logger.warning(f"Stream {self.config.id} already running")
                return
            
            self._status.is_running = True
            self._status.video_connected = True
            self._status.connection_state = ConnectionState.CONNECTED
            self._status.error = None
            self._status.last_audio_time = datetime.now() # Initialize watchdog timer

        logger.info(f"Starting stream worker for {self.config.name} ({self.config.id})")
        self._stop_event.clear()
        
        self._emit_status_event()

        if self.config.whisper_enabled:
            self._audio_thread = threading.Thread(
                target=self._audio_loop,
                name=f"audio-{self.config.id}",
                daemon=True
            )
            self._audio_thread.start()
            logger.info(f"Audio thread started for stream {self.config.id}")
        else:
            logger.info(f"Whisper disabled for stream {self.config.id}, no audio thread")

    def stop(self) -> None:
        """Stop the stream worker."""
        with self._status_lock:
             if not self._status.is_running:
                return
             self._status.is_running = False

        logger.info(f"Stopping stream worker for {self.config.name} ({self.config.id})")
        self._stop_event.set()

        if self._ffmpeg_process:
            self._cleanup_ffmpeg(self._ffmpeg_process)
            self._ffmpeg_process = None

        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        self._update_status(
            video_connected=False,
            audio_connected=False,
            whisper_connected=False,
            connection_state=ConnectionState.STOPPED
        )
        self._emit_status_event()

    def _audio_loop(self) -> None:
        """Audio extraction and WhisperLive connection loop."""
        logger.info(f"Audio thread started for stream {self.config.id}")

        while not self._stop_event.is_set():
            try:
                # Update watchdog timestamp periodically to prevent false restarts during backoff
                with self._status_lock:
                    self._status.last_audio_time = datetime.now()
                
                asyncio.run(self._whisper_connection())
                self._whisper_reconnect_attempts = 0
            except Exception as e:
                logger.error(f"Audio loop error for stream {self.config.id}: {e}")
                self._update_status(whisper_connected=False)

            if not self._stop_event.is_set():
                backoff_index = min(
                    self._whisper_reconnect_attempts,
                    len(WHISPER_RECONNECT_BACKOFF) - 1
                )
                delay = WHISPER_RECONNECT_BACKOFF[backoff_index]
                self._whisper_reconnect_attempts += 1
                
                with self._status_lock:
                    self._status.whisper_reconnects += 1
                    # Refresh watchdog while waiting so we don't get killed during normal backoff
                    self._status.last_audio_time = datetime.now() 

                logger.info(
                    f"WhisperLive reconnecting in {delay}s "
                    f"(attempt {self._whisper_reconnect_attempts}) for stream {self.config.id}"
                )
                
                # Sleep in chunks to allow fast interrupt
                for _ in range(delay * 10):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)

        logger.info(f"Audio thread stopped for stream {self.config.id}")

    def _read_ffmpeg_stderr(self, process: subprocess.Popen) -> None:
        """Read FFmpeg stderr to prevent buffer blocking and log errors."""
        try:
            while process.poll() is None and not self._stop_event.is_set():
                line = process.stderr.readline()
                if line:
                    decoded = line.decode().strip()
                    if decoded:
                        # Log only warnings/errors, not every frame
                        if "error" in decoded.lower() or "warning" in decoded.lower():
                            logger.warning(f"FFmpeg [{self.config.id}]: {decoded}")
        except Exception as e:
            logger.debug(f"FFmpeg stderr reader ended: {e}")

    def _get_audio_source_url(self) -> str:
        """Get the audio source URL.
        
        Using go2rtc's internal RTSP restream ensures go2rtc stays active
        and provides a consistent source for the transcription worker.
        """
        go2rtc_rtsp_port = int(os.getenv("GO2RTC_RTSP_PORT", "8955"))
        go2rtc_stream_name = f"camera_{self.config.id}"
        return f"rtsp://localhost:{go2rtc_rtsp_port}/{go2rtc_stream_name}"

    async def _whisper_connection(self) -> None:
        """Connect to WhisperLive and stream audio."""
        whisper_url = f"ws://{self.whisper_host}:{self.whisper_port}"
        logger.info(f"Connecting to WhisperLive at {whisper_url}")

        audio_source = self._get_audio_source_url()

        # FFmpeg command: Extracts audio from go2rtc RTSP restream
        # WhisperLive server expects 16kHz Mono Float32 (f32le)
        # volume=0.8 and loudnorm to provide clean balanced signal
        ffmpeg_cmd = [
            "ffmpeg",
            "-loglevel", "quiet",
            "-rtsp_transport", "tcp",
            "-i", audio_source,
            "-vn",
            "-af", "volume=0.8,aresample=async=1,loudnorm",
            "-c:a", "pcm_f32le",
            "-ar", "16000",
            "-ac", "1",
            "-f", "f32le",
            "pipe:1"
        ]

        ffmpeg_process = None
        try:
            async with websockets.connect(whisper_url) as ws:
                self._status.whisper_connected = True
                self._whisper_reconnect_attempts = 0
                logger.info(f"Connected to WhisperLive for stream {self.config.id}")

                # Handshake: tiny.en for speed; Sensitive VAD settings
                config_msg = {
                    "uid": f"wallflower_{self.config.id}_{int(time.time())}",
                    "language": "en",
                    "task": "transcribe",
                    "model": "tiny.en",
                    "use_vad": True,
                    "vad_parameters": {
                        "onset": 0.1,
                        "offset": 0.1,
                    },
                    "chunk_size": 1.0
                }
                await ws.send(json.dumps(config_msg))
                logger.info(f"Handshake sent (Sensitive VAD, Float32) for stream {self.config.id}")

                ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=10**6
                )
                self._ffmpeg_process = ffmpeg_process
                self._status.audio_connected = True
                self._emit_status_event()

                send_task = asyncio.create_task(self._send_audio(ws, ffmpeg_process))
                recv_task = asyncio.create_task(self._receive_transcripts(ws))

                done, pending = await asyncio.wait(
                    [send_task, recv_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    try:
                        await task
                    except Exception as e:
                        logger.error(f"Task failed: {e}")

                for task in pending:
                    task.cancel()

        except Exception as e:
            logger.error(f"WhisperLive connection error for stream {self.config.id}: {e}")
        finally:
            self._status.whisper_connected = False
            self._status.audio_connected = False
            self._ffmpeg_process = None
            self._emit_status_event()
            if ffmpeg_process:
                self._cleanup_ffmpeg(ffmpeg_process)

    async def _send_audio(self, ws, ffmpeg_process: subprocess.Popen) -> None:
        """Send audio chunks to WhisperLive with diagnostic sampling."""
        # 1.0s blocks (64000 bytes @ 16kHz Float32 Mono)
        chunk_size = 64000 
        chunks_sent = 0

        while not self._stop_event.is_set():
            if ffmpeg_process.poll() is not None:
                break

            try:
                audio_chunk = await asyncio.to_thread(ffmpeg_process.stdout.read, chunk_size)
                if not audio_chunk:
                    break

                chunks_sent += 1
                if chunks_sent % 30 == 1: # Log every 30 seconds
                    import numpy as np
                    samples = np.frombuffer(audio_chunk, dtype=np.float32)
                    max_val = np.max(np.abs(samples)) if len(samples) > 0 else 0
                    logger.info(f"Stream {self.config.id} Audio Probe (F32): Chunk={chunks_sent}, Max Amplitude={max_val:.4f}")

                await ws.send(audio_chunk)
                
                with self._status_lock:
                    self._status.last_audio_time = datetime.now()

            except Exception as e:
                logger.error(f"Send audio error: {e}")
                break

            await asyncio.sleep(0.01)

    async def _receive_transcripts(self, ws) -> None:
        """Receive transcripts from WhisperLive and persist to database."""
        while not self._stop_event.is_set():
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(message)
                
                logger.info(f"Received from WhisperLive for stream {self.config.id}: {data}")

                segments_to_process = []
                if "text" in data:
                    segments_to_process.append(data)
                elif "segments" in data and isinstance(data["segments"], list):
                    segments_to_process.extend(data["segments"])

                for seg_data in segments_to_process:
                    text = seg_data.get("text", "").strip()
                    if not text:
                        continue
                        
                    start_time = float(seg_data.get("start", 0.0))
                    is_final = seg_data.get("is_final", seg_data.get("completed", False))
                    
                    # Deduplication: Only process 'final' segments once
                    if is_final:
                        segment_id = f"{start_time:.2f}_{text}"
                        if segment_id in self._processed_segment_ids:
                            continue
                        self._processed_segment_ids.add(segment_id)
                        # Keep memory usage in check
                        if len(self._processed_segment_ids) > 1000:
                            self._processed_segment_ids.clear() 

                    segment = TranscriptSegment(
                        text=text,
                        start_time=start_time,
                        end_time=float(seg_data.get("end", 0.0)),
                        is_final=is_final
                    )

                    with self._transcript_lock:
                        self._transcript_segments.append(segment)
                        if len(self._transcript_segments) > 100:
                            self._transcript_segments = self._transcript_segments[-100:]

                    self._status.last_transcript = segment.text

                    if segment.is_final:
                        transcript_service.add(TranscriptCreate(
                            stream_id=self.config.id,
                            text=segment.text,
                            start_time=segment.start_time,
                            end_time=segment.end_time,
                            is_final=True,
                        ))

                        if getattr(self.config, 'save_transcripts_to_file', False):
                            self._write_transcript_to_file(segment)

                    if self.on_transcript:
                        self.on_transcript(self.config.id, segment)

                    event_broadcaster.emit_transcript(self.config.id, {
                        "text": segment.text,
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "is_final": segment.is_final,
                    })

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error receiving transcript: {e}")
                break

        transcript_service.flush()
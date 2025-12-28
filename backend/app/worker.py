"""Stream worker for TheWallflower.

Handles audio extraction from RTSP streams for WhisperLive transcription.

With go2rtc integration:
- go2rtc handles ALL video streaming (RTSP → WebRTC/MJPEG)
- This worker ONLY handles audio extraction for Whisper transcription
- Audio is extracted from go2rtc's RTSP restream (localhost:8654)
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

        # Status
        self._status = StreamStatus(stream_id=config.id)

        # Transcript buffer
        self._transcript_segments: List[TranscriptSegment] = []
        self._transcript_lock = threading.Lock()

        # Reconnection tracking
        self._whisper_reconnect_attempts = 0

    def _emit_status_event(self) -> None:
        """Emit current status via SSE."""
        status = self.status
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
            # Connection tracking (for audio/Whisper)
            "connection_state": status.connection_state.value,
            "retry_count": status.retry_count,
            "next_retry_time": status.next_retry_time.isoformat() if status.next_retry_time else None,
        })

    @property
    def status(self) -> StreamStatus:
        """Get current stream status with thread health."""
        # Video is handled by go2rtc - always "connected" when running
        self._status.video_thread_alive = self._status.is_running
        # Audio thread health
        self._status.audio_thread_alive = (
            self._audio_thread is not None and self._audio_thread.is_alive()
        )
        return self._status

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
            # Determine file path
            if getattr(self.config, 'transcript_file_path', None):
                file_path = self.config.transcript_file_path
            else:
                # Default path: /data/transcripts/[stream-name].txt
                safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.config.name)
                file_path = f"/data/transcripts/{safe_name}.txt"

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Format timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Append to file
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {segment.text}\n")

        except Exception as e:
            logger.error(f"Failed to write transcript to file: {e}")

    def start(self) -> None:
        """Start the stream worker.

        Video streaming is handled by go2rtc (added via stream_manager).
        This only starts the audio thread for Whisper transcription.
        """
        if self._status.is_running:
            logger.warning(f"Stream {self.config.id} already running")
            return

        logger.info(f"Starting stream worker for {self.config.name} ({self.config.id})")
        self._stop_event.clear()
        self._status.is_running = True
        self._status.video_connected = True  # go2rtc handles video
        self._status.connection_state = ConnectionState.CONNECTED
        self._status.error = None
        self._emit_status_event()

        # Start audio thread if whisper is enabled
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
        if not self._status.is_running:
            return

        logger.info(f"Stopping stream worker for {self.config.name} ({self.config.id})")
        self._stop_event.set()
        self._status.is_running = False

        # Stop FFmpeg process if running
        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()
                self._ffmpeg_process.wait()
            except Exception as e:
                logger.error(f"Error stopping FFmpeg: {e}")
            self._ffmpeg_process = None

        # Wait for audio thread to finish
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        self._status.video_connected = False
        self._status.audio_connected = False
        self._status.whisper_connected = False
        self._status.connection_state = ConnectionState.STOPPED
        self._emit_status_event()

    def _audio_loop(self) -> None:
        """Audio extraction and WhisperLive connection loop with exponential backoff."""
        logger.info(f"Audio thread started for stream {self.config.id}")

        while not self._stop_event.is_set():
            try:
                # Run the async whisper connection in this thread
                asyncio.run(self._whisper_connection())
                # Reset reconnect attempts on successful connection that ended gracefully
                self._whisper_reconnect_attempts = 0
            except Exception as e:
                logger.error(f"Audio loop error for stream {self.config.id}: {e}")
                self._status.whisper_connected = False

            if not self._stop_event.is_set():
                # Exponential backoff for reconnection
                backoff_index = min(
                    self._whisper_reconnect_attempts,
                    len(WHISPER_RECONNECT_BACKOFF) - 1
                )
                delay = WHISPER_RECONNECT_BACKOFF[backoff_index]
                self._whisper_reconnect_attempts += 1
                self._status.whisper_reconnects += 1

                logger.info(
                    f"WhisperLive reconnecting in {delay}s "
                    f"(attempt {self._whisper_reconnect_attempts}) for stream {self.config.id}"
                )
                time.sleep(delay)

        logger.info(f"Audio thread stopped for stream {self.config.id}")

    def _read_ffmpeg_stderr(self, process: subprocess.Popen) -> None:
        """Read FFmpeg stderr to prevent buffer blocking and log errors."""
        try:
            while process.poll() is None and not self._stop_event.is_set():
                line = process.stderr.readline()
                if line:
                    decoded = line.decode().strip()
                    if decoded:
                        logger.warning(f"FFmpeg [{self.config.id}]: {decoded}")
        except Exception as e:
            logger.debug(f"FFmpeg stderr reader ended: {e}")

    def _get_audio_source_url(self) -> str:
        """Get the audio source URL, preferring go2rtc restream.

        go2rtc provides a local RTSP restream that's more efficient:
        - Single connection to camera (go2rtc handles it)
        - Better reconnection handling
        - Lower latency local access

        Note: Port 8654 (not 8554) to avoid conflict with Frigate.
        """
        go2rtc_rtsp_port = int(os.getenv("GO2RTC_RTSP_PORT", "8654"))
        go2rtc_stream_name = f"camera_{self.config.id}"
        go2rtc_url = f"rtsp://localhost:{go2rtc_rtsp_port}/{go2rtc_stream_name}"

        # Try go2rtc first, fall back to direct RTSP if needed
        # In production, go2rtc should always be available
        return go2rtc_url

    async def _whisper_connection(self) -> None:
        """Connect to WhisperLive and stream audio."""
        whisper_url = f"ws://{self.whisper_host}:{self.whisper_port}"
        logger.info(f"Connecting to WhisperLive at {whisper_url}")

        # Get audio source URL (prefers go2rtc restream)
        audio_source = self._get_audio_source_url()
        logger.info(f"Audio source for stream {self.config.id}: {audio_source}")

        # FFmpeg command to extract audio from RTSP and output raw PCM
        # Using go2rtc restream provides single camera connection
        ffmpeg_cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",  # TCP for local connection to go2rtc
            "-i", audio_source,
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # 16-bit PCM
            "-ar", "16000",  # 16kHz sample rate (required by Whisper)
            "-ac", "1",  # Mono
            "-f", "s16le",  # Raw PCM format
            "-loglevel", "warning",  # Show warnings and errors
            "pipe:1"  # Output to stdout
        ]

        ffmpeg_process = None
        stderr_thread = None

        try:
            async with websockets.connect(whisper_url) as ws:
                self._status.whisper_connected = True
                self._whisper_reconnect_attempts = 0  # Reset on successful connect
                logger.info(f"Connected to WhisperLive for stream {self.config.id}")

                # Start FFmpeg process
                ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=10**6
                )
                self._ffmpeg_process = ffmpeg_process
                self._status.audio_connected = True
                self._status.ffmpeg_restarts += 1
                self._emit_status_event()

                # Start stderr reader thread to prevent buffer blocking
                stderr_thread = threading.Thread(
                    target=self._read_ffmpeg_stderr,
                    args=(ffmpeg_process,),
                    name=f"ffmpeg-stderr-{self.config.id}",
                    daemon=True
                )
                stderr_thread.start()

                # Create tasks for sending audio and receiving transcripts
                send_task = asyncio.create_task(
                    self._send_audio(ws, ffmpeg_process)
                )
                recv_task = asyncio.create_task(
                    self._receive_transcripts(ws)
                )

                # Wait for either task to complete (or stop event)
                done, pending = await asyncio.wait(
                    [send_task, recv_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WhisperLive connection closed for stream {self.config.id}")
        except ConnectionRefusedError:
            logger.warning(f"WhisperLive connection refused for stream {self.config.id}")
        except Exception as e:
            logger.error(f"WhisperLive error for stream {self.config.id}: {e}")
        finally:
            self._status.whisper_connected = False
            self._status.audio_connected = False
            self._ffmpeg_process = None
            self._emit_status_event()
            if ffmpeg_process:
                try:
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    ffmpeg_process.kill()
                    ffmpeg_process.wait()

    async def _send_audio(self, ws, ffmpeg_process: subprocess.Popen) -> None:
        """Send audio chunks to WhisperLive."""
        chunk_size = 4096  # 16-bit samples at 16kHz

        while not self._stop_event.is_set():
            # Check if FFmpeg process is still running
            if ffmpeg_process.poll() is not None:
                logger.warning(f"FFmpeg process ended for stream {self.config.id}")
                break

            # Read audio chunk from FFmpeg
            audio_chunk = ffmpeg_process.stdout.read(chunk_size)
            if not audio_chunk:
                break

            # Track last successful audio time
            self._status.last_audio_time = datetime.now()

            # Send to WhisperLive
            try:
                await ws.send(audio_chunk)
            except Exception as e:
                logger.error(f"Error sending audio: {e}")
                break

            # Small delay to prevent overwhelming the connection
            await asyncio.sleep(0.01)

    async def _receive_transcripts(self, ws) -> None:
        """Receive transcripts from WhisperLive and persist to database."""
        while not self._stop_event.is_set():
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(message)

                # Parse WhisperLive response
                if "text" in data:
                    segment = TranscriptSegment(
                        text=data.get("text", ""),
                        start_time=data.get("start", 0.0),
                        end_time=data.get("end", 0.0),
                        is_final=data.get("is_final", False)
                    )

                    # Keep in-memory buffer for real-time display
                    with self._transcript_lock:
                        self._transcript_segments.append(segment)
                        # Keep only last 100 segments in memory
                        if len(self._transcript_segments) > 100:
                            self._transcript_segments = self._transcript_segments[-100:]

                    self._status.last_transcript = segment.text

                    # Persist final transcripts to database
                    if segment.is_final and segment.text.strip():
                        transcript_service.add(TranscriptCreate(
                            stream_id=self.config.id,
                            text=segment.text,
                            start_time=segment.start_time,
                            end_time=segment.end_time,
                            is_final=True,
                        ))

                        # Write to file if configured
                        if getattr(self.config, 'save_transcripts_to_file', False):
                            self._write_transcript_to_file(segment)

                    # Callback for real-time updates
                    if self.on_transcript:
                        self.on_transcript(self.config.id, segment)

                    # Emit via SSE for real-time frontend updates
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

        # Flush any pending transcripts when connection ends
        transcript_service.flush()

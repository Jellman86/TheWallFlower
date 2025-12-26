"""Stream worker for TheWallflower.

Handles video capture and audio extraction from RTSP streams,
running frame processors and connecting to WhisperLive for transcription.
"""

import asyncio
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Callable
import json

import cv2
import numpy as np
import websockets

from app.models import StreamConfig
from app.processors import FrameProcessor, MjpegStreamer, SnapshotProcessor

logger = logging.getLogger(__name__)

# Reconnection backoff configuration
WHISPER_RECONNECT_BACKOFF = [1, 2, 5, 10, 30, 60]  # seconds
FFMPEG_RESTART_DELAY = 2  # seconds
THREAD_HEALTH_CHECK_INTERVAL = 10  # seconds


@dataclass
class TranscriptSegment:
    """A segment of transcribed text."""
    text: str
    start_time: float
    end_time: float
    is_final: bool = False


@dataclass
class StreamStatus:
    """Current status of a stream worker."""
    stream_id: int
    is_running: bool = False
    video_connected: bool = False
    audio_connected: bool = False
    whisper_connected: bool = False
    fps: float = 0.0
    error: Optional[str] = None
    last_transcript: Optional[str] = None
    # Health tracking
    video_thread_alive: bool = False
    audio_thread_alive: bool = False
    ffmpeg_restarts: int = 0
    whisper_reconnects: int = 0
    last_frame_time: Optional[datetime] = None
    last_audio_time: Optional[datetime] = None


class StreamWorker:
    """Worker that processes a single RTSP stream.

    Manages two threads:
    - Video thread: Captures frames via OpenCV, runs processors
    - Audio thread: Extracts audio via FFmpeg, sends to WhisperLive
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
        self._video_thread: Optional[threading.Thread] = None
        self._audio_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None

        # Status
        self._status = StreamStatus(stream_id=config.id)

        # Processors
        self._processors: List[FrameProcessor] = []
        self._mjpeg_streamer: Optional[MjpegStreamer] = None

        # Transcript buffer
        self._transcript_segments: List[TranscriptSegment] = []
        self._transcript_lock = threading.Lock()

        # Reconnection tracking
        self._whisper_reconnect_attempts = 0

    @property
    def status(self) -> StreamStatus:
        """Get current stream status with thread health."""
        if self._mjpeg_streamer:
            self._status.fps = self._mjpeg_streamer.fps
        # Update thread health status
        self._status.video_thread_alive = (
            self._video_thread is not None and self._video_thread.is_alive()
        )
        self._status.audio_thread_alive = (
            self._audio_thread is not None and self._audio_thread.is_alive()
        )
        return self._status

    @property
    def mjpeg_streamer(self) -> Optional[MjpegStreamer]:
        """Get the MJPEG streamer for this worker."""
        return self._mjpeg_streamer

    @property
    def transcripts(self) -> List[TranscriptSegment]:
        """Get all transcript segments."""
        with self._transcript_lock:
            return list(self._transcript_segments)

    def start(self) -> None:
        """Start the stream worker."""
        if self._status.is_running:
            logger.warning(f"Stream {self.config.id} already running")
            return

        logger.info(f"Starting stream worker for {self.config.name} ({self.config.id})")
        self._stop_event.clear()
        self._status.is_running = True
        self._status.error = None

        # Initialize processors
        self._setup_processors()

        # Start video thread
        self._video_thread = threading.Thread(
            target=self._video_loop,
            name=f"video-{self.config.id}",
            daemon=True
        )
        self._video_thread.start()

        # Start audio thread if whisper is enabled
        if self.config.whisper_enabled:
            self._audio_thread = threading.Thread(
                target=self._audio_loop,
                name=f"audio-{self.config.id}",
                daemon=True
            )
            self._audio_thread.start()

    def stop(self) -> None:
        """Stop the stream worker."""
        if not self._status.is_running:
            return

        logger.info(f"Stopping stream worker for {self.config.name} ({self.config.id})")
        self._stop_event.set()
        self._status.is_running = False

        # Stop processors
        for processor in self._processors:
            try:
                processor.stop()
            except Exception as e:
                logger.error(f"Error stopping processor {processor.name}: {e}")

        # Wait for threads to finish
        if self._video_thread and self._video_thread.is_alive():
            self._video_thread.join(timeout=5.0)
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        self._status.video_connected = False
        self._status.audio_connected = False
        self._status.whisper_connected = False

    def _setup_processors(self) -> None:
        """Initialize frame processors."""
        self._processors = []

        # Always add MJPEG streamer
        self._mjpeg_streamer = MjpegStreamer(self.config.id)
        self._processors.append(self._mjpeg_streamer)

        # Add snapshot processor
        self._processors.append(SnapshotProcessor(self.config.id))

        # Future: Add face detection processor if enabled
        # if self.config.face_detection_enabled:
        #     self._processors.append(FaceDetectionProcessor(self.config.id))

        # Start all processors
        for processor in self._processors:
            processor.start()

    def _video_loop(self) -> None:
        """Main video capture and processing loop."""
        logger.info(f"Video thread started for stream {self.config.id}")

        cap = None
        retry_count = 0
        max_retries = 5
        processor_failures: dict[str, int] = {}  # Track processor failure counts

        while not self._stop_event.is_set():
            try:
                # Open video capture
                if cap is None or not cap.isOpened():
                    logger.info(f"Connecting to RTSP: {self.config.rtsp_url}")
                    cap = cv2.VideoCapture(self.config.rtsp_url)

                    if not cap.isOpened():
                        retry_count += 1
                        if retry_count > max_retries:
                            self._status.error = "Failed to connect to RTSP stream"
                            logger.error(f"Stream {self.config.id}: {self._status.error}")
                            break
                        time.sleep(2)
                        continue

                    self._status.video_connected = True
                    self._status.error = None
                    retry_count = 0
                    logger.info(f"Connected to stream {self.config.id}")

                # Read frame
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Failed to read frame from stream {self.config.id}")
                    cap.release()
                    cap = None
                    self._status.video_connected = False
                    time.sleep(1)
                    continue

                # Track last successful frame time
                self._status.last_frame_time = datetime.now()

                # Run frame through all processors with isolation
                for processor in self._processors:
                    try:
                        frame = processor.process(frame)
                        # Reset failure count on success
                        processor_failures[processor.name] = 0
                    except Exception as e:
                        # Track failures per processor
                        processor_failures[processor.name] = processor_failures.get(processor.name, 0) + 1
                        failure_count = processor_failures[processor.name]

                        if failure_count <= 3:
                            logger.error(f"Processor {processor.name} error ({failure_count}): {e}")
                        elif failure_count == 4:
                            logger.error(f"Processor {processor.name} failing repeatedly, suppressing logs")
                        # Continue with other processors even if one fails

            except Exception as e:
                logger.error(f"Video loop error for stream {self.config.id}: {e}")
                self._status.error = str(e)
                if cap:
                    cap.release()
                    cap = None
                time.sleep(2)

        # Cleanup
        if cap:
            cap.release()
        self._status.video_connected = False
        logger.info(f"Video thread stopped for stream {self.config.id}")

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

    async def _whisper_connection(self) -> None:
        """Connect to WhisperLive and stream audio."""
        whisper_url = f"ws://{self.whisper_host}:{self.whisper_port}"
        logger.info(f"Connecting to WhisperLive at {whisper_url}")

        # FFmpeg command to extract audio from RTSP and output raw PCM
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", self.config.rtsp_url,
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
        """Receive transcripts from WhisperLive."""
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

                    with self._transcript_lock:
                        self._transcript_segments.append(segment)
                        # Keep only last 100 segments
                        if len(self._transcript_segments) > 100:
                            self._transcript_segments = self._transcript_segments[-100:]

                    self._status.last_transcript = segment.text

                    # Callback for real-time updates
                    if self.on_transcript:
                        self.on_transcript(self.config.id, segment)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error receiving transcript: {e}")
                break

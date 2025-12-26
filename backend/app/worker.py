"""Stream worker for TheWallflower.

Handles video capture and audio extraction from RTSP streams,
running frame processors and connecting to WhisperLive for transcription.
"""

import asyncio
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Callable
import json

import cv2
import numpy as np
import websockets

from app.models import StreamConfig
from app.processors import FrameProcessor, MjpegStreamer, SnapshotProcessor

logger = logging.getLogger(__name__)


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

        # Status
        self._status = StreamStatus(stream_id=config.id)

        # Processors
        self._processors: List[FrameProcessor] = []
        self._mjpeg_streamer: Optional[MjpegStreamer] = None

        # Transcript buffer
        self._transcript_segments: List[TranscriptSegment] = []
        self._transcript_lock = threading.Lock()

    @property
    def status(self) -> StreamStatus:
        """Get current stream status."""
        if self._mjpeg_streamer:
            self._status.fps = self._mjpeg_streamer.fps
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

                # Run frame through all processors
                for processor in self._processors:
                    try:
                        frame = processor.process(frame)
                    except Exception as e:
                        logger.error(f"Processor {processor.name} error: {e}")

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
        """Audio extraction and WhisperLive connection loop."""
        logger.info(f"Audio thread started for stream {self.config.id}")

        while not self._stop_event.is_set():
            try:
                # Run the async whisper connection in this thread
                asyncio.run(self._whisper_connection())
            except Exception as e:
                logger.error(f"Audio loop error for stream {self.config.id}: {e}")
                self._status.whisper_connected = False

            if not self._stop_event.is_set():
                time.sleep(5)  # Retry delay

        logger.info(f"Audio thread stopped for stream {self.config.id}")

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
            "-loglevel", "error",
            "pipe:1"  # Output to stdout
        ]

        ffmpeg_process = None

        try:
            async with websockets.connect(whisper_url) as ws:
                self._status.whisper_connected = True
                logger.info(f"Connected to WhisperLive for stream {self.config.id}")

                # Start FFmpeg process
                ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=10**6
                )
                self._status.audio_connected = True

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

        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WhisperLive connection closed for stream {self.config.id}")
        except Exception as e:
            logger.error(f"WhisperLive error for stream {self.config.id}: {e}")
        finally:
            self._status.whisper_connected = False
            self._status.audio_connected = False
            if ffmpeg_process:
                ffmpeg_process.terminate()
                ffmpeg_process.wait()

    async def _send_audio(self, ws, ffmpeg_process: subprocess.Popen) -> None:
        """Send audio chunks to WhisperLive."""
        chunk_size = 4096  # 16-bit samples at 16kHz

        while not self._stop_event.is_set():
            # Read audio chunk from FFmpeg
            audio_chunk = ffmpeg_process.stdout.read(chunk_size)
            if not audio_chunk:
                break

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

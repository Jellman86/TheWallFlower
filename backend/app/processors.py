"""Frame processors for TheWallflower video pipeline.

This module defines the abstract FrameProcessor interface and concrete
implementations for processing video frames. The modular design allows
easy addition of new processors (face detection, motion detection, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import asyncio
import time
import numpy as np


class FrameProcessor(ABC):
    """Abstract base class for frame processors.

    All video processing plugins must implement this interface.
    Processors are called sequentially for each frame in the pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this processor."""
        pass

    @abstractmethod
    def process(self, frame: np.ndarray) -> np.ndarray:
        """Process a video frame.

        Args:
            frame: BGR image as numpy array (OpenCV format)

        Returns:
            Processed frame (may be modified or unchanged)
        """
        pass

    def start(self) -> None:
        """Called when the stream starts. Override for setup logic."""
        pass

    def stop(self) -> None:
        """Called when the stream stops. Override for cleanup logic."""
        pass


class MjpegStreamer(FrameProcessor):
    """Broadcasts frames to connected MJPEG clients.

    This processor encodes frames as JPEG and makes them available
    for streaming to web clients via the /api/video/{id} endpoint.
    """

    def __init__(self, stream_id: int, quality: int = 80):
        self._stream_id = stream_id
        self._quality = quality
        self._frame: Optional[bytes] = None
        self._frame_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._running = False
        self._fps = 0.0
        self._last_frame_time = 0.0

    @property
    def name(self) -> str:
        return f"mjpeg_streamer_{self._stream_id}"

    @property
    def stream_id(self) -> int:
        return self._stream_id

    @property
    def current_frame(self) -> Optional[bytes]:
        """Get the latest JPEG-encoded frame."""
        return self._frame

    @property
    def fps(self) -> float:
        """Current frames per second."""
        return self._fps

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Encode frame as JPEG and store for streaming."""
        import cv2

        # Calculate FPS
        now = time.time()
        if self._last_frame_time > 0:
            delta = now - self._last_frame_time
            if delta > 0:
                self._fps = 1.0 / delta
        self._last_frame_time = now

        # Encode to JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._quality]
        success, encoded = cv2.imencode('.jpg', frame, encode_params)

        if success:
            self._frame = encoded.tobytes()
            # Signal waiting clients that a new frame is available
            try:
                self._frame_event.set()
            except RuntimeError:
                pass  # Event loop may not be running in this thread

        return frame  # Pass through unchanged

    async def get_frame(self) -> Optional[bytes]:
        """Async method to get the next frame (for streaming endpoint)."""
        self._frame_event.clear()
        try:
            await asyncio.wait_for(self._frame_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        return self._frame

    def start(self) -> None:
        self._running = True
        self._last_frame_time = 0.0

    def stop(self) -> None:
        self._running = False
        self._frame = None


class SnapshotProcessor(FrameProcessor):
    """Captures periodic snapshots for thumbnail generation.

    Future use: Can be extended for face detection snapshots.
    """

    def __init__(self, stream_id: int, interval_seconds: float = 5.0):
        self._stream_id = stream_id
        self._interval = interval_seconds
        self._last_snapshot_time = 0.0
        self._latest_snapshot: Optional[bytes] = None

    @property
    def name(self) -> str:
        return f"snapshot_{self._stream_id}"

    @property
    def latest_snapshot(self) -> Optional[bytes]:
        """Get the most recent snapshot."""
        return self._latest_snapshot

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Capture snapshot at configured interval."""
        import cv2

        now = time.time()
        if now - self._last_snapshot_time >= self._interval:
            # Encode snapshot
            success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if success:
                self._latest_snapshot = encoded.tobytes()
            self._last_snapshot_time = now

        return frame

    def start(self) -> None:
        self._last_snapshot_time = 0.0

    def stop(self) -> None:
        pass

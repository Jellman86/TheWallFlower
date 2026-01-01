import os
import time
import signal
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from app.models import StreamConfig
from app.config import settings

logger = logging.getLogger(__name__)

class RecordingWorker:
    """Worker that manages an FFmpeg process for continuous recording."""

    def __init__(self, config: StreamConfig):
        self.config = config
        self._stop_event = threading.Event()
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Base directory for recordings: /data/recordings/{stream_id}
        # Note: Container mounts /data to host's data directory.
        self.base_dir = Path("/data/recordings") / str(config.id)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Internal state
        self._is_running = False

    def start(self):
        """Start the recording thread."""
        with self._lock:
            if self._is_running:
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name=f"rec-worker-{self.config.id}",
                daemon=True
            )
            self._thread.start()
            self._is_running = True
            logger.info(f"Stream {self.config.id}: Recording worker starting")

    def stop(self):
        """Stop the recording thread and FFmpeg process."""
        with self._lock:
            if not self._is_running:
                return
            
            self._stop_event.set()
        
        self._terminate_ffmpeg()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            
        with self._lock:
            self._is_running = False
            self._thread = None
        
        logger.info(f"Stream {self.config.id}: Recording worker stopped")

    def _terminate_ffmpeg(self):
        """Gracefully terminate the FFmpeg process."""
        if self._process and self._process.poll() is None:
            logger.info(f"Stream {self.config.id}: Stopping recording FFmpeg...")
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Stream {self.config.id}: FFmpeg did not exit, killing...")
                self._process.kill()
            self._process = None

    def _loop(self):
        """Main loop managing the FFmpeg process."""
        while not self._stop_event.is_set():
            try:
                self._run_ffmpeg()
            except Exception as e:
                logger.error(f"Stream {self.config.id}: Recording error: {e}")
                
            # If FFmpeg exits or crashes, wait before restarting (unless stopped)
            if not self._stop_event.is_set():
                time.sleep(5)

    def _run_ffmpeg(self):
        """Configure and run the FFmpeg process."""
        # Use go2rtc internal loopback
        # URL pattern: rtsp://localhost:{port}/camera_{id}
        stream_name = f"camera_{self.config.id}"
        input_url = f"rtsp://localhost:{settings.go2rtc_rtsp_port}/{stream_name}"
        
        # Output pattern: /data/recordings/{stream_id}/%Y-%m-%d_%H-%M-%S.mp4
        # ffmpeg -f segment -segment_time 900 -strftime 1 ...
        output_pattern = f"{self.base_dir}/%Y-%m-%d_%H-%M-%S.mp4"
        
        # 15 minutes = 900 seconds
        segment_time = "900" 
        
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", input_url,
            "-c", "copy",     # Direct copy (no transcoding)
            "-map", "0",      # Map all streams
            "-f", "segment",
            "-segment_time", segment_time,
            "-segment_format", "mp4",
            "-strftime", "1",
            "-reset_timestamps", "1",
            output_pattern
        ]
        
        logger.info(f"Stream {self.config.id}: Starting recording (segmented)")
        
        # Run FFmpeg
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        
        # wait() blocks until the process exits.
        # This is where the thread spends most of its time.
        _, stderr = self._process.communicate()
        
        if self._stop_event.is_set():
            # Expected shutdown
            return

        if self._process.returncode != 0:
            err_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Stream {self.config.id}: FFmpeg exited with code {self._process.returncode}. Stderr: {err_msg}")
            raise Exception(f"FFmpeg crashed: {err_msg}")
        else:
            logger.info(f"Stream {self.config.id}: FFmpeg exited normally")

"""Face detection worker.

Periodically fetches frames from go2rtc and runs face detection.
"""

import threading
import time
import logging
import httpx
import os
from datetime import datetime

from app.models import StreamConfig
from app.services.detection.face_service import face_service
from app.config import settings

logger = logging.getLogger(__name__)

class FaceDetectionWorker:
    """Worker that handles face detection for a stream."""

    def __init__(self, config: StreamConfig):
        self.config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread = None
        self._is_running = False
        
        # Stats
        self.last_detection_time = None
        self.faces_detected = 0
        self.errors = 0

    def start(self):
        """Start the face detection loop."""
        if self._is_running:
            return

        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name=f"face-{self.config.id}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"Face detection worker started for stream {self.config.id}")

    def stop(self):
        """Stop the worker."""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info(f"Face detection worker stopped for stream {self.config.id}")

    def _loop(self):
        """Main detection loop."""
        # go2rtc frame URL (internal)
        # http://localhost:8954/api/frame.jpeg?src=camera_{id}
        go2rtc_url = f"http://{settings.go2rtc_host}:{settings.go2rtc_port}/api/frame.jpeg?src=camera_{self.config.id}"
        
        interval = self.config.face_detection_interval or 1.0
        
        # Use a persistent client
        with httpx.Client(timeout=5.0) as client:
            while not self._stop_event.is_set():
                start_time = time.time()
                
                try:
                    # Fetch frame
                    response = client.get(go2rtc_url)
                    if response.status_code == 200:
                        # Process frame
                        events = face_service.process_frame(self.config.id, response.content)
                        
                        if events:
                            self.faces_detected += len(events)
                            logger.info(f"Stream {self.config.id}: Detected {len(events)} faces")
                        
                        self.last_detection_time = datetime.now()
                    else:
                        # go2rtc might not be ready or stream is down
                        pass

                except Exception as e:
                    self.errors += 1
                    # Don't log every error to avoid spamming if stream is down
                    if self.errors % 60 == 1: 
                        logger.error(f"Face worker error for stream {self.config.id}: {e}")

                # Sleep for remainder of interval
                elapsed = time.time() - start_time
                sleep_time = max(0.1, interval - elapsed)
                
                # Sleep in small chunks to allow fast stop
                chunks = int(sleep_time / 0.1)
                for _ in range(chunks):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                if not self._stop_event.is_set():
                    time.sleep(sleep_time % 0.1)

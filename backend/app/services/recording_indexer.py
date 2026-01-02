import logging
import os
import threading
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.models import Recording
from app.services.recording_service import recording_service

logger = logging.getLogger(__name__)

class RecordingEventHandler(FileSystemEventHandler):
    """Handles file system events for recordings."""
    
    def on_closed(self, event):
        """Called when a file is closed (finished writing)."""
        if event.is_directory or not event.src_path.endswith('.mp4'):
            return
        
        # Give a tiny delay to ensure lock release/flush? Usually on_closed is safe.
        self.process_file(event.src_path)

    def process_file(self, file_path: str):
        path = Path(file_path)
        try:
            # Expected path: /data/recordings/{stream_id}/{filename}
            from app.config import settings
            base_recordings_path = Path(settings.data_path) / "recordings"

            # So structure is: {data_path}/recordings/{stream_id}/2026-01-01_12-00-00.mp4
            
            try:
                rel_path = path.relative_to(base_recordings_path)
            except ValueError:
                # File is not in our recordings dir?
                return
                
            parts = rel_path.parts
            
            if len(parts) < 2:
                return 
            
            stream_id = int(parts[0])
            
            # Check if already indexed
            if recording_service.get_recording_by_path(str(rel_path)):
                return

            # Parse filename for start time
            # Filename format: %Y-%m-%d_%H-%M-%S.mp4
            filename = path.name
            start_str = path.stem # 2026-01-01_14-15-00
            start_time = datetime.strptime(start_str, "%Y-%m-%d_%H-%M-%S")
            
            # Get actual duration from file
            duration = self.get_duration(file_path)
            if duration is None:
                # Fallback: estimate from file size? No, that's unreliable.
                # Just log warning and skip? Or assume segment time (900s)?
                # Better to skip indexing corrupt files.
                logger.warning(f"Could not determine duration for {file_path}, skipping index.")
                return
                
            end_time = start_time + timedelta(seconds=duration)
            file_size = path.stat().st_size
            
            if file_size == 0:
                logger.warning(f"Skipping empty recording file: {file_path}")
                return
            
            # Create DB entry
            rec = Recording(
                stream_id=stream_id,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                file_path=str(rel_path),
                file_size_bytes=file_size,
                retention_locked=False
            )
            
            recording_service.create_recording(rec)
            logger.info(f"Indexed recording: {rel_path} ({duration:.1f}s)")
            
        except Exception as e:
            logger.error(f"Error processing recording file {file_path}: {e}")

    def get_duration(self, file_path: str) -> Optional[float]:
        try:
            # use ffprobe
            cmd = [
                "ffprobe", 
                "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout.strip()
                if output and output != "N/A":
                    return float(output)
        except Exception as e:
            # logger.debug(f"ffprobe failed for {file_path}: {e}")
            pass
        return None

class RecordingIndexer:
    def __init__(self):
        from app.config import settings
        self.observer = Observer()
        self.handler = RecordingEventHandler()
        self.watch_dir = os.path.join(settings.data_path, "recordings")
        
        # Ensure dir exists
        os.makedirs(self.watch_dir, exist_ok=True)

    def start(self):
        logger.info(f"Starting recording indexer watching {self.watch_dir}")
        self.observer.schedule(self.handler, self.watch_dir, recursive=True)
        self.observer.start()
        
        # Scan for existing files on startup
        self.scan_existing()

    def stop(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def scan_existing(self):
        t = threading.Thread(target=self._scan_thread, daemon=True)
        t.start()
        
    def _scan_thread(self):
        logger.info("Scanning for unindexed recordings...")
        count = 0
        try:
            for root, dirs, files in os.walk(self.watch_dir):
                for file in files:
                    if file.endswith(".mp4"):
                        path = os.path.join(root, file)
                        try:
                            rel_path = str(Path(path).relative_to(self.watch_dir))
                            if not recording_service.get_recording_by_path(rel_path):
                                self.handler.process_file(path)
                                count += 1
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Error during existing file scan: {e}")
            
        if count > 0:
            logger.info(f"Backfilled {count} recordings")

recording_indexer = RecordingIndexer()

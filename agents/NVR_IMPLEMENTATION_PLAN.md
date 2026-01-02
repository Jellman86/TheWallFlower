# NVR (Network Video Recorder) Implementation Plan
**Date:** 2026-01-01
**Status:** **COMPLETE**

## 1. Executive Summary
We have implemented continuous 24/7 video recording for TheWallflower. The system records streams to local disk in segmented files, indexes them in the database for quick retrieval, and provides a playback interface.

**Core Philosophy:** "Write once, Read many."
We prioritize stable, low-CPU writing (Direct Copy) and efficient indexing.

---

## 2. Architecture (Implemented)

### A. Recording Engine (The "Writer")
**`RecordingWorker`**
*   **Source:** `go2rtc` RTSP loopback (`rtsp://localhost:8955/{stream_id}`)
*   **Codec:** `copy` (No transcoding - extremely low CPU usage).
*   **Container:** `MP4` (Fragmented).
*   **Segmentation:** 15-minute chunks (900 seconds).
*   **Path:** `/data/recordings/{stream_id}/%Y-%m-%d_%H-%M-%S.mp4`

### B. The Indexer (The "Librarian")
**`RecordingIndexer`**
*   **Trigger:** `watchdog` monitors `/data/recordings` for `IN_CLOSE_WRITE` events.
*   **Action:**
    1.  Parses filename for start time.
    2.  Uses `ffprobe` to get exact duration.
    3.  Inserts into `Recordings` table (skips 0-byte files).
*   **Backfill:** Scans directory on startup to catch up on missed files.

### C. Cleanup
**`StreamManager` Maintenance Task**
*   Runs every minute.
*   Checks `StreamConfig.recording_retention_days` (default 7).
*   Deletes old files and database records.

---

## 3. Database Schema

**Table: `Recording`**

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `int` (PK) | Unique ID |
| `stream_id` | `int` (FK) | Relates to Stream |
| `start_time` | `datetime` | UTC start time |
| `end_time` | `datetime` | UTC end time (start + duration) |
| `file_path` | `str` | Relative path (e.g., `1/2026-01-01_12-00-00.mp4`) |
| `file_size_bytes` | `int` | File size |
| `retention_locked` | `bool` | If true, auto-cleanup won't delete this (Future) |

---

## 4. API Endpoints

*   `GET /api/streams/{id}/recordings?start={ts}&end={ts}` - List segments.
*   `GET /api/streams/{id}/recordings/dates` - List available dates.
*   `GET /api/recordings/{id}/stream` - Stream video file (supports Range requests).
*   `DELETE /api/recordings/{id}` - Delete recording.

---

## 5. Frontend UI

*   **Mode:** "Focus View" on Stream Card.
*   **Tabs:** Switch between "Live" and "Recordings".
*   **Components:**
    *   **Calendar:** Select date.
    *   **Clip List:** List of 15-min segments with duration/size.
    *   **Player:** Native HTML5 video player with controls.

---

## 6. Future Improvements

1.  **Timeline UI:** Visual scrubber bar instead of a list of clips.
2.  **Smart Search:** "Jump to where someone said 'Hello'".
3.  **Export:** Download clip with burned-in subtitles.

# Face Detection & Recognition Implementation Plan
**Date:** 2026-01-01
**Status:** **COMPLETE**

## 1. Executive Summary
We have integrated local, privacy-focused face detection and recognition into TheWallflower. The goal is to identify "Who is at the door?" and annotate events, without relying on external cloud services.

**Key Technologies:**
- **Engine:** `insightface` (Python) running on ONNX Runtime.
- **Models:** `buffalo_l` (high accuracy) or `buffalo_s` (speed).
- **Input:** Frames extracted from `go2rtc` (MJPEG/Snapshot).
- **Storage:** SQLite for metadata, local filesystem for thumbnails.

---

## 2. Competitive Landscape & Inspiration

| Project | Approach | Pros | Cons |
|---------|----------|------|------|
| **Frigate** | Object detection first (Coral), then face recognition via add-on (Double Take). | Extremely efficient. | Complex setup (MQTT, separate containers). |
| **Double Take** | Unified UI proxying to CompreFace/DeepStack. | Great UI, aggregates multiple detectors. | Requires external detector setup. |
| **CompreFace** | Dedicated API server (Exadel). | Very accurate. | Heavy Java/Python container. |

**TheWallflower Approach:**
"Batteries Included". A single Python worker within the existing backend container. No extra containers to manage.

---

## 3. Architecture (Implemented)

### A. The `FaceWorker`
A background thread (`FaceDetectionWorker`) runs per stream if enabled.

*   **Logic:**
    1.  Fetches frames from `go2rtc` API (`http://localhost:{port}/api/frame.jpeg?src={camera}`).
    2.  Uses `FaceService` (singleton) to detect faces using InsightFace.
    3.  Matches embeddings against known faces in the database (Cosine Similarity > 0.5).
    4.  Saves events to `face_events` table and thumbnails to `/data/faces/`.

### B. Database Schema (`models.py`)

*   **`Face`**: Stores known/unknown identities and their reference embedding.
*   **`FaceEvent`**: Logs every detection with timestamp, confidence, and snapshot.

---

## 4. Implementation Steps (Completed)

### Phase 1: Dependencies & Core Logic (Backend)
*   [x] Added `insightface` and `onnxruntime`.
*   [x] Implemented `FaceService` with lazy loading and caching.

### Phase 2: The Worker (Backend)
*   [x] Created `app/workers/face_worker.py`.
*   [x] Connected to `StreamManager` lifecycle.

### Phase 3: UI Integration (Frontend)
*   [x] **Settings:** "Enable Face Detection" checkbox.
*   [x] **Faces Page:** Gallery of detected faces (`/faces`).
*   [x] **Management:** Rename "Unknown" faces to "Known" or delete them.

---

## 5. Technical Considerations

*   **CPU Usage:** Face recognition is heavy.
    *   *Mitigation:* Default interval is 1.0s (configurable).
*   **Model Storage:** InsightFace downloads models to `~/.insightface`.
*   **Thread Safety:** `FaceService` uses a lock for model loading.

---

## 6. API Endpoints

*   `GET /api/faces` - List known/unknown faces.
*   `PATCH /api/faces/{id}` - Rename/Merge a face.
*   `DELETE /api/faces/{id}` - Delete a face.
*   `GET /api/events/faces` - List face detection events.
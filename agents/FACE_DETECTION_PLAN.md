# Face Detection & Recognition Implementation Plan
**Date:** 2026-01-01
**Status:** Planning

## 1. Executive Summary
We will integrate local, privacy-focused face detection and recognition into TheWallflower. The goal is to identify "Who is at the door?" and annotate events, without relying on external cloud services.

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

## 3. Architecture

### A. The `FaceWorker`
A new background thread (or process) per stream, similar to the audio `StreamWorker`.

```python
class FaceWorker:
    def __init__(self, config):
        self.model = InsightFace(name='buffalo_l')
        self.fps = 1.0  # Limit to 1 frame per second to save CPU

    def loop(self):
        while running:
            # 1. Fetch frame from go2rtc (localhost:8955/frame.jpeg)
            frame = self.get_frame()
            
            # 2. Detect Faces
            faces = self.model.get(frame)
            
            # 3. For each face:
            for face in faces:
                # Compare with DB embeddings
                identity = self.recognize(face.embedding)
                
                # If known, log event
                # If unknown, log "Unknown Face" event + save thumbnail
```

### B. Database Schema (`models.py`)

```python
class Face(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    name: str = "Unknown"
    embedding: bytes  # Serialized numpy array (512-float)
    thumbnail_path: str
    created_at: datetime

class FaceEvent(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    stream_id: int
    face_id: Optional[int] = Field(foreign_key="face.id")
    confidence: float
    timestamp: datetime
    snapshot_path: str  # Full frame snapshot
```

---

## 4. Implementation Steps

### Phase 1: Dependencies & Core Logic (Backend)
1.  Add `insightface` and `onnxruntime` to `requirements.txt`.
2.  Update `Dockerfile` (might need system libs for cv2/onnx).
3.  Implement `FaceService`:
    -   Loading models (cache them).
    -   `match_face(embedding)`: Calculate cosine similarity.
    -   `register_face(name, embedding)`: Save to DB.

### Phase 2: The Worker (Backend)
1.  Create `app/workers/face_worker.py`.
2.  Connect to `StreamConfig.face_detection_enabled`.
3.  Fetch frames from `go2rtc` API (`http://localhost:{port}/api/frame.jpeg?src={camera}`).
4.  Run inference.

### Phase 3: UI Integration (Frontend)
1.  **Settings:** Enable "Face Detection" in Stream Settings (already placeholder).
2.  **Faces Page:** New route `/faces`.
    -   Grid of "Unknown" faces.
    -   Click to name -> Moves to "Known".
3.  **Stream View:**
    -   Show "Recent Face" pill/overlay.

---

## 5. Technical Considerations

*   **CPU Usage:** Face recognition is heavy.
    *   *Mitigation:* Limit to 0.5 - 1.0 FPS.
    *   *Mitigation:* Use `buffalo_s` (small model) by default.
*   **Model Storage:** InsightFace downloads models to `~/.insightface`. We need to persist this or bake it into the image.
*   **Thread Safety:** The ONNX runtime is generally thread-safe, but we should manage the model instance carefully (singleton).

---

## 6. API Endpoints

*   `GET /api/faces` - List known/unknown faces.
*   `PATCH /api/faces/{id}` - Rename/Merge a face.
*   `DELETE /api/faces/{id}` - Delete a face.
*   `GET /api/events/faces` - List face detection events.

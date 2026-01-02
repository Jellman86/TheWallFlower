# Face Recognition Upgrade Plan
**Date:** 2026-01-02
**Status:** **COMPLETE**
**Priority:** HIGH
**Inspired by:** Frigate NVR 0.16+ Face Recognition

---

## 1. OBJECTIVE

Upgrade TheWallflower's face recognition to support Frigate-style pretraining:
- Upload folders of named photos for training
- Multiple embeddings per person for robustness
- Training UI to review and assign detected faces
- Configurable thresholds via settings
- API endpoints for programmatic face management

---

## 2. CURRENT STATE ANALYSIS

### What We Have
```
backend/app/
├── models.py                    # Face, FaceEvent, FaceRead models
├── services/detection/
│   └── face_service.py          # FaceService singleton with InsightFace
├── workers/
│   └── face_worker.py           # Periodic frame capture + detection
└── routers/
    └── faces.py                 # Basic CRUD API
```

### Current Limitations
| Issue | Impact |
|-------|--------|
| Single embedding per face | Poor recognition with varied angles/lighting |
| No pretraining | Must wait for camera to capture faces |
| Auto-register unknowns | Database fills with duplicates |
| Fixed thresholds | No tuning for different environments |
| No training UI | Can only name faces, not train them |

---

## 3. TARGET ARCHITECTURE

### 3.1 Folder Structure
```
/data/faces/
├── known/                       # Pre-trained known faces
│   ├── John_Smith/
│   │   ├── photo1.jpg
│   │   ├── photo2.jpg
│   │   └── photo3.jpg
│   ├── Jane_Doe/
│   │   └── profile.jpg
│   └── .trained/                # Marker files after processing
│       ├── John_Smith.json      # Metadata + embedding stats
│       └── Jane_Doe.json
├── unknown/                     # Auto-captured unknown faces
│   └── {face_id}/
│       └── {timestamp}.jpg
└── train/                       # Pending review (from camera)
    └── {stream_id}/
        └── {timestamp}_{face_id}.jpg
```

### 3.2 Database Schema Changes

```sql
-- New table for multiple embeddings per person
CREATE TABLE face_embeddings (
    id INTEGER PRIMARY KEY,
    face_id INTEGER NOT NULL REFERENCES faces(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL,           -- Pickled numpy array
    source TEXT NOT NULL,              -- 'upload', 'camera', 'pretrain'
    quality_score FLOAT DEFAULT 0.0,   -- Face detection confidence
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_path TEXT                    -- Path to source image
);

-- Add index for fast lookups
CREATE INDEX idx_face_embeddings_face_id ON face_embeddings(face_id);

-- Modify faces table
ALTER TABLE faces ADD COLUMN embedding_count INTEGER DEFAULT 1;
ALTER TABLE faces ADD COLUMN avg_embedding BLOB;  -- Averaged embedding for fast matching
```

### 3.3 New Models

```python
# models.py additions

class FaceEmbedding(SQLModel, table=True):
    """Individual embedding for a face (supports multiple per person)."""
    __tablename__ = "face_embeddings"

    id: Optional[int] = Field(default=None, primary_key=True)
    face_id: int = Field(foreign_key="faces.id", index=True)
    embedding: bytes
    source: str = Field(default="camera")  # 'upload', 'camera', 'pretrain'
    quality_score: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    image_path: Optional[str] = None


class FaceTrainingRequest(SQLModel):
    """Request to upload training images."""
    name: str
    images: List[bytes]  # Base64 encoded images


class FaceRecognitionConfig(SQLModel):
    """Configurable thresholds."""
    recognition_threshold: float = 0.5    # Match known faces
    unknown_threshold: float = 0.6        # Deduplicate unknowns
    min_face_area: int = 500              # Minimum face size in pixels
    max_embeddings_per_face: int = 30     # Prevent overfitting
    auto_register_unknown: bool = True    # Auto-create unknown entries
```

---

## 4. IMPLEMENTATION PHASES

### Phase 1: Database Migration & Multi-Embedding Support
**Estimated Complexity:** Medium

#### Tasks:
1. Create Alembic migration for `face_embeddings` table
2. Update `Face` model with `embedding_count` and `avg_embedding`
3. Migrate existing single embeddings to `face_embeddings` table
4. Update `FaceService._update_cache()` to load all embeddings
5. Implement embedding averaging for fast initial matching

#### Files to Modify:
- `backend/app/models.py`
- `backend/migrations/versions/` (new migration)
- `backend/app/services/detection/face_service.py`

#### Migration Script:
```python
def upgrade():
    # Create face_embeddings table
    op.create_table('face_embeddings', ...)

    # Migrate existing embeddings
    conn = op.get_bind()
    faces = conn.execute(text("SELECT id, embedding FROM faces")).fetchall()
    for face_id, embedding in faces:
        conn.execute(text("""
            INSERT INTO face_embeddings (face_id, embedding, source)
            VALUES (:face_id, :embedding, 'legacy')
        """), {"face_id": face_id, "embedding": embedding})

    # Add new columns to faces
    op.add_column('faces', sa.Column('embedding_count', sa.Integer(), default=1))
    op.add_column('faces', sa.Column('avg_embedding', sa.LargeBinary(), nullable=True))
```

---

### Phase 2: Folder-Based Pretraining
**Estimated Complexity:** Medium

#### Tasks:
1. Create `FacePretrainer` service class
2. Implement folder scanning on startup
3. Process images: detect face, extract embedding, store
4. Create `.trained/{name}.json` metadata files
5. Add environment variable `FACE_PRETRAIN_PATH`
6. Handle incremental updates (new photos added)

#### New File: `backend/app/services/detection/face_pretrainer.py`

```python
class FacePretrainer:
    """Scans folder structure and pretrains face recognition."""

    def __init__(self, base_path: str = "/data/faces/known"):
        self.base_path = Path(base_path)
        self.trained_path = self.base_path / ".trained"
        self.face_service = face_service

    def scan_and_train(self) -> Dict[str, int]:
        """Scan folders and train faces. Returns {name: num_images}."""
        results = {}

        for person_dir in self.base_path.iterdir():
            if person_dir.is_dir() and not person_dir.name.startswith('.'):
                name = person_dir.name.replace('_', ' ')
                count = self._train_person(name, person_dir)
                results[name] = count

        return results

    def _train_person(self, name: str, folder: Path) -> int:
        """Process all images for a person."""
        metadata_file = self.trained_path / f"{folder.name}.json"
        existing = self._load_metadata(metadata_file)

        count = 0
        for img_path in folder.glob("*.jpg"):
            if str(img_path) in existing.get("processed", []):
                continue

            # Load and process image
            img = cv2.imread(str(img_path))
            faces = self.face_service.detect_faces(img)

            if len(faces) == 1:
                self._add_embedding(name, faces[0], img_path, "pretrain")
                existing.setdefault("processed", []).append(str(img_path))
                count += 1
            elif len(faces) > 1:
                logger.warning(f"Multiple faces in {img_path}, skipping")

        self._save_metadata(metadata_file, existing)
        return count
```

#### Startup Integration:
```python
# main.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup ...

    # Pretrain faces from folder
    if settings.face_pretrain_enabled:
        pretrainer = FacePretrainer(settings.face_pretrain_path)
        results = pretrainer.scan_and_train()
        logger.info(f"Pretrained faces: {results}")

    yield
```

---

### Phase 3: Enhanced Matching Algorithm
**Estimated Complexity:** Medium

#### Tasks:
1. Implement multi-embedding matching (check all embeddings per person)
2. Add area-weighted scoring (larger faces = higher confidence)
3. Implement quality-based filtering (blur detection)
4. Add configurable thresholds via environment/database
5. Optimize with averaged embedding for initial filtering

#### Updated Matching Logic:
```python
def recognize_face(self, detected_face, min_area: int = 500) -> Tuple[str, int, float]:
    """Match against all embeddings with weighted scoring."""

    # Skip small faces
    bbox = detected_face.bbox
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    if area < min_area:
        return "Unknown", None, 0.0

    target = detected_face.embedding
    target_norm = np.linalg.norm(target)

    best_match = {"name": "Unknown", "id": None, "score": 0.0}

    for face in self.known_faces_cache:
        # Quick filter with averaged embedding
        avg_score = self._cosine_sim(target, face.avg_embedding_numpy, target_norm)
        if avg_score < self.config.recognition_threshold * 0.8:
            continue

        # Detailed matching against all embeddings
        scores = []
        for emb in face.embeddings:
            score = self._cosine_sim(target, emb.embedding_numpy, target_norm)
            # Weight by quality
            weighted = score * (0.5 + 0.5 * emb.quality_score)
            scores.append(weighted)

        # Use top-k average (robust to outliers)
        top_k = sorted(scores, reverse=True)[:5]
        final_score = sum(top_k) / len(top_k) if top_k else 0.0

        if final_score > best_match["score"]:
            best_match = {"name": face.name, "id": face.id, "score": final_score}

    # Apply threshold
    if best_match["score"] < self.config.recognition_threshold:
        return "Unknown", None, best_match["score"]

    return best_match["name"], best_match["id"], best_match["score"]
```

---

### Phase 4: API Endpoints
**Estimated Complexity:** Low

#### New Endpoints:

```python
# routers/faces.py additions

@router.post("/{name}/train")
async def upload_training_images(
    name: str,
    files: List[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    """Upload training images for a person (Frigate-compatible)."""
    face = get_or_create_face(session, name, is_known=True)

    processed = 0
    for file in files:
        img_bytes = await file.read()
        result = face_service.process_training_image(face.id, img_bytes, "upload")
        if result:
            processed += 1

    return {"name": name, "processed": processed, "total": len(files)}


@router.post("/reprocess")
async def reprocess_all_faces(session: Session = Depends(get_session)):
    """Recompute averaged embeddings for all faces."""
    count = face_service.recompute_averages()
    return {"reprocessed": count}


@router.get("/train", response_model=List[FaceTrainCandidate])
async def list_training_candidates(
    stream_id: Optional[int] = None,
    limit: int = 50
):
    """List faces pending review/training."""
    return face_service.get_training_candidates(stream_id, limit)


@router.post("/train/{candidate_id}/assign/{face_name}")
async def assign_training_candidate(
    candidate_id: int,
    face_name: str,
    session: Session = Depends(get_session)
):
    """Assign a training candidate to a known person."""
    return face_service.assign_candidate(candidate_id, face_name)


@router.get("/config", response_model=FaceRecognitionConfig)
async def get_face_config():
    """Get current face recognition configuration."""
    return face_service.config


@router.patch("/config", response_model=FaceRecognitionConfig)
async def update_face_config(config: FaceRecognitionConfig):
    """Update face recognition configuration."""
    face_service.update_config(config)
    return face_service.config
```

---

### Phase 5: Training UI
**Estimated Complexity:** Medium-High

#### New Components:

1. **FaceLibrary.svelte** - Main face management page
   - Grid view of known faces with thumbnails
   - Upload button for training images
   - Delete/rename actions

2. **FaceTraining.svelte** - Review pending detections
   - Show unassigned faces from cameras
   - Quick-assign to existing person or create new
   - Batch operations

3. **FaceSettings.svelte** - Configuration panel
   - Threshold sliders
   - Toggle auto-register
   - Pretrain folder status

#### UI Wireframe:
```
+----------------------------------------------------------+
|  Face Library                              [+ Add Person] |
+----------------------------------------------------------+
|  Known Faces                                              |
|  +--------+  +--------+  +--------+  +--------+           |
|  |  John  |  |  Jane  |  | David  |  |  +Add  |           |
|  | [img]  |  | [img]  |  | [img]  |  |        |           |
|  | 5 imgs |  | 3 imgs |  | 12 imgs|  |        |           |
|  +--------+  +--------+  +--------+  +--------+           |
+----------------------------------------------------------+
|  Pending Review (24 faces)                    [Bulk Assign]|
|  +------+ +------+ +------+ +------+ +------+ +------+    |
|  |[img] | |[img] | |[img] | |[img] | |[img] | |[img] |    |
|  |75%   | |82%   | |91%   | |68%   | |73%   | |88%   |    |
|  |[John]| |[Jane]| |[New] | |[Skip]| |[John]| |[???] |    |
|  +------+ +------+ +------+ +------+ +------+ +------+    |
+----------------------------------------------------------+
|  Settings                                                 |
|  Recognition Threshold: [====O====] 0.50                  |
|  Unknown Threshold:     [=====O===] 0.60                  |
|  Min Face Area:         [===O=====] 500px                 |
|  [x] Auto-register unknown faces                          |
|  Pretrain Folder: /data/faces/known (3 people, 15 images) |
+----------------------------------------------------------+
```

#### Frontend Files:
```
frontend/src/lib/components/
├── faces/
│   ├── FaceLibrary.svelte      # Main grid view
│   ├── FaceCard.svelte         # Individual face card
│   ├── FaceTraining.svelte     # Pending review list
│   ├── FaceUploader.svelte     # Drag-drop image upload
│   └── FaceSettings.svelte     # Config panel
└── routes/
    └── faces/
        └── +page.svelte        # /faces route
```

---

## 5. CONFIGURATION

### Environment Variables
```bash
# Face Recognition Settings
FACE_PRETRAIN_ENABLED=true
FACE_PRETRAIN_PATH=/data/faces/known
FACE_RECOGNITION_THRESHOLD=0.5
FACE_UNKNOWN_THRESHOLD=0.6
FACE_MIN_AREA=500
FACE_MAX_EMBEDDINGS=30
FACE_AUTO_REGISTER_UNKNOWN=true
FACE_SAVE_TRAINING_IMAGES=true
FACE_TRAINING_PATH=/data/faces/train
```

### Config Class
```python
# config.py additions
class FaceSettings(BaseSettings):
    face_pretrain_enabled: bool = True
    face_pretrain_path: str = "/data/faces/known"
    face_recognition_threshold: float = 0.5
    face_unknown_threshold: float = 0.6
    face_min_area: int = 500
    face_max_embeddings: int = 30
    face_auto_register_unknown: bool = True
    face_save_training_images: bool = True
    face_training_path: str = "/data/faces/train"
```

---

## 6. TESTING PLAN

### Unit Tests
```python
# tests/test_face_service.py

def test_multi_embedding_matching():
    """Test matching with multiple embeddings per person."""

def test_folder_pretraining():
    """Test scanning and training from folder structure."""

def test_embedding_averaging():
    """Test averaged embedding computation."""

def test_quality_filtering():
    """Test blur/quality detection."""

def test_threshold_configuration():
    """Test configurable thresholds."""
```

### Integration Tests
```python
def test_pretrain_on_startup():
    """Test pretraining runs on application startup."""

def test_api_upload_training_images():
    """Test POST /api/faces/{name}/train endpoint."""

def test_api_assign_candidate():
    """Test training candidate assignment."""
```

### Manual Testing Checklist
```
[ ] Create /data/faces/known/Test_Person/ with 5 photos
[ ] Restart container, verify pretraining logs
[ ] Check face appears in UI with correct embedding count
[ ] Test recognition against live camera
[ ] Upload additional training images via API
[ ] Verify averaged embedding updates
[ ] Test threshold changes take effect
[ ] Test training UI workflow
```

---

## 7. MIGRATION PATH

### For Existing Installations

1. **Backup existing faces table**
2. **Run migration** - Creates `face_embeddings`, migrates data
3. **No action required** - Existing faces continue to work
4. **Optional** - Add pretrain folder for improved recognition

### Breaking Changes
- None - fully backward compatible
- New features are opt-in via configuration

---

## 8. TIMELINE ESTIMATE

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Phase 1 | Database + Multi-embedding | Medium |
| Phase 2 | Folder Pretraining | Medium |
| Phase 3 | Enhanced Matching | Medium |
| Phase 4 | API Endpoints | Low |
| Phase 5 | Training UI | Medium-High |

**Recommended Order:** 1 → 2 → 3 → 4 → 5

---

## 9. REFERENCES

- [Frigate Face Recognition Docs](https://docs.frigate.video/configuration/face_recognition/)
- [Frigate GitHub Discussion #6735](https://github.com/blakeblackshear/frigate/discussions/6735)
- [ArcFace Paper](https://arxiv.org/abs/1801.07698)
- [InsightFace Documentation](https://insightface.ai/)
- [LearnOpenCV ArcFace Guide](https://learnopencv.com/face-recognition-with-arcface/)

---

## 10. OPEN QUESTIONS

1. **GPU Acceleration** - Should we support CUDA/OpenVINO for faster inference?
2. **Face Clustering** - Auto-group similar unknown faces?
3. **Liveness Detection** - Prevent photo spoofing?
4. **Privacy Controls** - Auto-delete faces after X days?
5. **Export/Import** - Backup face library to file?

---

**Plan Status:** Ready for Implementation

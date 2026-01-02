"""Service for Face Detection and Recognition using InsightFace."""

import os
import logging
import threading
import numpy as np
import cv2
import pickle
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from sqlmodel import Session, select

try:
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False

from app.db import engine
from app.models import Face, FaceEvent
from app.config import settings

logger = logging.getLogger(__name__)

# Constants
COSINE_THRESHOLD = 0.5  # Similarity threshold for matching known faces (0.0 - 1.0)
UNKNOWN_DEDUP_THRESHOLD = 0.6  # Higher threshold for deduplicating unknown faces
MODEL_NAME = "buffalo_l" # "buffalo_l" (better) or "buffalo_s" (faster)
FACE_DB_CACHE_TTL = 60 # Seconds to cache known face embeddings in memory

class FaceService:
    """Singleton service for Face Detection and Recognition."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FaceService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.app = None
        self.model_loaded = False
        self.known_faces_cache: List[Face] = []
        self.face_embeddings_cache: Dict[int, np.ndarray] = {}
        self.last_cache_update = 0
        self._initialized = True
        
        if not INSIGHTFACE_AVAILABLE:
            logger.warning("InsightFace not installed. Face detection disabled.")
            return

    def load_model(self):
        """Load the InsightFace model (lazy loading)."""
        if self.model_loaded:
            return
            
        with self._lock:
            if self.model_loaded:
                return
                
            logger.info(f"Loading InsightFace model: {MODEL_NAME}...")
            try:
                # providers=['CUDAExecutionProvider', 'CPUExecutionProvider'] if GPU else CPU
                # We default to CPU for compatibility, but ONNX Runtime will use GPU if available/installed
                self.app = FaceAnalysis(name=MODEL_NAME, providers=['CPUExecutionProvider'])
                self.app.prepare(ctx_id=0, det_size=(640, 640))
                self.model_loaded = True
                logger.info("InsightFace model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load InsightFace model: {e}")
                self.app = None

    def _update_cache(self):
        """Update local cache of known face embeddings."""
        import time
        now = time.time()
        if now - self.last_cache_update < FACE_DB_CACHE_TTL:
            return

        try:
            with Session(engine) as session:
                # Fetch all faces
                faces = session.exec(select(Face)).all()
                self.known_faces_cache = []
                # Keep existing embeddings for faces we already have
                new_embeddings_cache = {}
                
                for face in faces:
                    try:
                        # Use average embedding if available, otherwise the primary one
                        embedding_to_load = face.avg_embedding if face.avg_embedding else face.embedding
                        
                        # Use a hash of the embedding to check if it changed
                        # (Simple optimization to avoid redundant pickle.loads)
                        new_embeddings_cache[face.id] = pickle.loads(embedding_to_load)
                        
                        self.known_faces_cache.append(face)
                    except Exception as e:
                        logger.error(f"Error deserializing embedding for face {face.id}: {e}")
                
                self.face_embeddings_cache = new_embeddings_cache
                self.last_cache_update = now
                logger.debug(f"Updated face cache: {len(self.known_faces_cache)} faces loaded.")
        except Exception as e:
            logger.error(f"Failed to update face cache: {e}")

    def detect_faces(self, frame_bgr: np.ndarray) -> List[Dict]:
        """Detect faces in a frame."""
        if not self.model_loaded:
            self.load_model()
            
        if not self.app:
            return []

        try:
            # InsightFace expects BGR image (OpenCV default)
            faces = self.app.get(frame_bgr)
            return faces
        except Exception as e:
            logger.error(f"Error during face detection: {e}")
            return []

    def recognize_face(self, detected_face) -> Tuple[str, Optional[int], float]:
        """Identify a detected face against the database.

        Returns:
            (name, face_id, confidence)
        """
        self._update_cache()

        best_match_name = "Unknown"
        best_match_id = None
        max_score = 0.0

        # Track best unknown match separately for deduplication
        best_unknown_id = None
        best_unknown_score = 0.0

        # Calculate similarity with all faces (known and unknown)
        target_embedding = detected_face.embedding
        target_norm = np.linalg.norm(target_embedding)

        for known_face in self.known_faces_cache:
            known_embedding = self.face_embeddings_cache.get(known_face.id)
            if known_embedding is None:
                continue
                
            known_norm = np.linalg.norm(known_embedding)

            # Cosine similarity
            score = np.dot(target_embedding, known_embedding) / (target_norm * known_norm)

            if score > max_score:
                max_score = score
                if score > COSINE_THRESHOLD:
                    best_match_name = known_face.name
                    best_match_id = known_face.id

            # Track best unknown match for deduplication
            if not known_face.is_known and score > best_unknown_score:
                best_unknown_score = score
                best_unknown_id = known_face.id

        # If no known match but strong unknown match, use that (deduplication)
        if best_match_id is None and best_unknown_score > UNKNOWN_DEDUP_THRESHOLD:
            best_match_id = best_unknown_id
            best_match_name = f"Unknown-{best_unknown_id}"
            max_score = best_unknown_score

        return best_match_name, best_match_id, float(max_score)

    def process_frame(self, stream_id: int, frame_bytes: bytes) -> List[FaceEvent]:
        """Process a frame: Detect -> Recognize -> Save Event."""
        if not self.model_loaded:
            self.load_model()
            
        # Decode image
        nparr = np.frombuffer(frame_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return []

        detected_faces = self.detect_faces(img)
        events = []
        
        with Session(engine) as session:
            for face in detected_faces:
                name, face_id, confidence = self.recognize_face(face)
                
                # If unknown and high quality detection, maybe register it as a new "Unknown" face?
                # For now, we only log events. Auto-registration logic can be complex (deduplication).
                # Implementation: If unknown, we create a new 'Unknown' Face entry to track it.
                
                if face_id is None:
                    # Create new Unknown face
                    new_face = Face(
                        name="Unknown",
                        embedding=pickle.dumps(face.embedding),
                        is_known=False
                    )
                    session.add(new_face)
                    session.commit()
                    session.refresh(new_face)

                    face_id = new_face.id
                    name = f"Unknown-{face_id}"  # Temp name for display

                    # Save thumbnail
                    self._save_thumbnail(img, face, face_id)
                    
                    # Save initial embedding
                    self._save_face_embedding(face_id, face.embedding, img, face)
                else:
                    # Update last_seen for matched face (known or deduplicated unknown)
                    matched_face = session.get(Face, face_id)
                    if matched_face:
                        matched_face.last_seen = datetime.now()
                        
                        # If face missing thumbnail (e.g. due to previous errors), save it now
                        if not matched_face.thumbnail_path:
                            self._save_thumbnail(img, face, face_id)
                            
                        session.add(matched_face)
                        
                        # Save this embedding too to improve recognition over time (limit to 50 per face)
                        if matched_face.embedding_count < 50:
                            self._save_face_embedding(face_id, face.embedding, img, face)

                # Save event snapshot (the full frame)
                snapshot_filename = f"event_{int(datetime.now().timestamp())}_{face_id}.jpg"
                snapshot_path = self._save_snapshot(img, snapshot_filename)

                # Create Event
                event = FaceEvent(
                    stream_id=stream_id,
                    face_id=face_id,
                    confidence=confidence,
                    face_name=name,
                    snapshot_path=snapshot_path
                )
                session.add(event)
                events.append(event)
            
            session.commit()
            
        return events

    def _save_snapshot(self, img, filename):
        """Save a full frame snapshot for an event."""
        try:
            snapshots_dir = os.path.join(settings.data_path, "snapshots")
            os.makedirs(snapshots_dir, exist_ok=True)
            path = os.path.join(snapshots_dir, filename)
            
            success = cv2.imwrite(path, img)
            if success:
                return path
            else:
                logger.error(f"cv2.imwrite failed for snapshot {path}")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
        return None

    def scan_known_faces(self):
        """Scan /data/faces/known/{name}/ for images to pre-train the model."""
        known_dir = os.path.join(settings.data_path, "faces", "known")
        if not os.path.exists(known_dir):
            os.makedirs(known_dir, exist_ok=True)
            return

        logger.info(f"Scanning for known faces in {known_dir}...")
        
        for name in os.listdir(known_dir):
            person_dir = os.path.join(known_dir, name)
            if not os.path.isdir(person_dir):
                continue
                
            for filename in os.listdir(person_dir):
                if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                    
                img_path = os.path.join(person_dir, filename)
                try:
                    img = cv2.imread(img_path)
                    if img is None:
                        continue
                        
                    faces = self.detect_faces(img)
                    if not faces:
                        logger.warning(f"No face detected in {img_path}")
                        continue
                        
                    # Use the largest face if multiple detected
                    face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                    
                    with Session(engine) as session:
                        # Find or create face
                        db_face = session.exec(select(Face).where(Face.name == name)).first()
                        if not db_face:
                            db_face = Face(
                                name=name,
                                embedding=pickle.dumps(face.embedding),
                                is_known=True
                            )
                            session.add(db_face)
                            session.commit()
                            session.refresh(db_face)
                            logger.info(f"Registered new face from disk: {name}")
                            # Save initial thumbnail
                            self._save_thumbnail(img, face, db_face.id)
                        
                        # Add embedding if not already at limit
                        if db_face.embedding_count < 50:
                            self._save_face_embedding(db_face.id, face.embedding, img, face)
                            
                except Exception as e:
                    logger.error(f"Error processing pretrain image {img_path}: {e}")

    def _save_thumbnail(self, img, face, face_id):
        """Save a cropped thumbnail of the face."""
        try:
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            # Add padding
            h, w, _ = img.shape
            pad_x = int((x2 - x1) * 0.2)
            pad_y = int((y2 - y1) * 0.2)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x)
            y2 = min(h, y2 + pad_y)
            
            crop = img[y1:y2, x1:x2]
            
            # Ensure directory exists
            faces_dir = os.path.join(settings.data_path, "faces")
            os.makedirs(faces_dir, exist_ok=True)
            path = os.path.join(faces_dir, f"{face_id}.jpg")
            
            # Write file and check success
            success = cv2.imwrite(path, crop)
            if not success:
                logger.error(f"cv2.imwrite failed for {path}")
                return
            
            # Update DB with path
            with Session(engine) as session:
                db_face = session.get(Face, face_id)
                if db_face:
                    db_face.thumbnail_path = path
                    session.add(db_face)
                    session.commit()
                    logger.debug(f"Saved thumbnail for face {face_id} to {path}")
                    
        except Exception as e:
            logger.error(f"Failed to save thumbnail: {e}")

    def _save_face_embedding(self, face_id: int, embedding: np.ndarray, img: Optional[np.ndarray] = None, face_obj: Optional[Dict] = None):
        """Save a new embedding for a face and update the average."""
        try:
            from app.models import FaceEmbedding
            
            embedding_bytes = pickle.dumps(embedding)
            image_path = None

            # Save a crop if image provided
            if img is not None and face_obj is not None:
                try:
                    bbox = face_obj.bbox.astype(int)
                    x1, y1, x2, y2 = bbox
                    h, w, _ = img.shape
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    crop = img[y1:y2, x1:x2]
                    
                    emb_dir = os.path.join(settings.data_path, "embeddings")
                    os.makedirs(emb_dir, exist_ok=True)
                    filename = f"{face_id}_{int(time.time()*1000)}.jpg"
                    image_path = os.path.join(emb_dir, filename)
                    cv2.imwrite(image_path, crop)
                except Exception as e:
                    logger.error(f"Failed to save embedding crop: {e}")
            
            with Session(engine) as session:
                # Save individual embedding
                new_emb = FaceEmbedding(
                    face_id=face_id,
                    embedding=embedding_bytes,
                    source="camera",
                    quality_score=0.0, # Future: calculate quality
                    image_path=image_path
                )
                session.add(new_emb)
                
                # Update Face summary stats
                db_face = session.get(Face, face_id)
                if db_face:
                    # Update count
                    db_face.embedding_count += 1
                    
                    # Update average embedding (simplified: running average)
                    if db_face.avg_embedding:
                        current_avg = pickle.loads(db_face.avg_embedding)
                        # New average = (old_avg * (count-1) + new_emb) / count
                        new_avg = (current_avg * (db_face.embedding_count - 1) + embedding) / db_face.embedding_count
                        db_face.avg_embedding = pickle.dumps(new_avg)
                    else:
                        db_face.avg_embedding = embedding_bytes
                        
                    session.add(db_face)
                
                session.commit()
        except Exception as e:
            logger.error(f"Failed to save face embedding: {e}")


face_service = FaceService()

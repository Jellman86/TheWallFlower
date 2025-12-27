# TheWallflower Development Plan

> A comprehensive roadmap to make TheWallflower robust, production-ready, and feature-complete.

**Version:** 1.0
**Created:** 2025-12-26
**Status:** Planning

---

## Table of Contents

1. [Current State Assessment](#current-state-assessment)
2. [Phase 1: Stability & Robustness](#phase-1-stability--robustness)
3. [Phase 2: Production Hardening](#phase-2-production-hardening)
4. [Phase 3: Core Feature Completion](#phase-3-core-feature-completion)
5. [Phase 4: Speaker Diarization](#phase-4-speaker-diarization)
6. [Phase 5: Advanced Features](#phase-5-advanced-features)
7. [Phase 6: Intel GPU & OpenVINO Support](#phase-6-intel-gpu--openvino-support)
8. [Technical Specifications](#technical-specifications)
9. [Architecture Evolution](#architecture-evolution)

---

## Current State Assessment

### What's Working (70-80% MVP Complete)

| Component | Status | Notes |
|-----------|--------|-------|
| Stream CRUD API | Complete | All endpoints functional |
| MJPEG Video Streaming | Complete | Real-time with FPS display |
| Stream Lifecycle | Complete | Start/stop/restart working |
| WhisperLive Integration | Basic | WebSocket connection works |
| SQLite Persistence | Complete | Stream configs stored |
| Docker Deployment | Complete | Multi-stage build |
| Svelte 5 Frontend | Complete | Modern runes syntax |

### Critical Gaps

| Issue | Severity | Impact |
|-------|----------|--------|
| No Authentication | High | Anyone can access/modify streams |
| Transcripts In-Memory Only | High | Lost on restart |
| FFmpeg stderr buffer | Medium | Can cause process hang |
| Polling instead of SSE/WS | Medium | Inefficient, high latency |
| No Input Validation | Medium | Security risk |
| No Tests | Medium | Regression risk |

---

## Phase 1: Stability & Robustness

**Goal:** Make the existing features bulletproof.

### 1.1 FFmpeg Process Management

**Problem:** FFmpeg stderr is piped but never read, can fill buffer and block.

**Solution:**
```python
# worker.py - Add stderr monitoring thread
def _monitor_ffmpeg_stderr(self):
    """Read FFmpeg stderr to prevent buffer blocking."""
    while self._running and self._audio_process:
        line = self._audio_process.stderr.readline()
        if line:
            log.debug("ffmpeg", output=line.decode().strip())
        elif self._audio_process.poll() is not None:
            break
```

**Tasks:**
- [ ] Add stderr reader thread in worker.py
- [ ] Implement FFmpeg process health monitoring
- [ ] Add automatic restart on FFmpeg crash
- [ ] Add FFmpeg timeout detection (no output for N seconds)

### 1.2 WhisperLive Connection Resilience

**Problem:** Basic reconnection, no heartbeat, can fail silently.

**Solution:**
```python
# Add keepalive and robust reconnection
WHISPER_KEEPALIVE_INTERVAL = 30  # seconds
WHISPER_RECONNECT_BACKOFF = [1, 2, 5, 10, 30, 60]  # exponential backoff
```

**Tasks:**
- [ ] Implement WebSocket heartbeat/ping
- [ ] Add exponential backoff for reconnection
- [ ] Track connection state separately from running state
- [ ] Add connection quality metrics (latency, drops)
- [ ] Handle WhisperLive protocol errors gracefully

### 1.3 Processor Pipeline Isolation

**Problem:** One failing processor blocks entire video pipeline.

**Solution:**
```python
# processors.py - Add timeout and isolation
def process_frame_safe(self, frame, timeout=0.1):
    """Process frame with timeout and exception isolation."""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.process, frame)
            return future.result(timeout=timeout)
    except TimeoutError:
        log.warning("processor_timeout", processor=self.__class__.__name__)
        return frame
    except Exception as e:
        log.error("processor_error", processor=self.__class__.__name__, error=str(e))
        return frame
```

**Tasks:**
- [ ] Wrap processor calls in try-except
- [ ] Add per-processor timeout
- [ ] Add processor health metrics
- [ ] Implement processor disable on repeated failures

### 1.4 Thread Health Monitoring

**Problem:** Worker threads can die silently.

**Tasks:**
- [ ] Add thread watchdog in stream_manager.py
- [ ] Implement automatic worker restart on thread death
- [ ] Add thread health endpoint to API
- [ ] Log thread lifecycle events

---

## Phase 2: Production Hardening

**Goal:** Make the system secure and production-ready.

### 2.1 Authentication & Authorization

**Approach:** JWT-based authentication with API keys for programmatic access.

**Database Schema Addition:**
```python
# models.py
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    api_key: Optional[str] = Field(default=None, index=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class StreamPermission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    stream_id: int = Field(foreign_key="stream.id")
    can_view: bool = Field(default=True)
    can_control: bool = Field(default=False)
    can_edit: bool = Field(default=False)
```

**Tasks:**
- [ ] Add User and Permission models
- [ ] Implement password hashing (argon2)
- [ ] Add JWT token generation/validation
- [ ] Create login/logout endpoints
- [ ] Add API key authentication option
- [ ] Implement permission checking middleware
- [ ] Add rate limiting (slowapi)
- [ ] Update frontend with login flow

### 2.2 Input Validation

**Tasks:**
- [ ] Add RTSP URL validation (regex + optional probe)
- [ ] Sanitize stream names (prevent XSS)
- [ ] Add request body size limits
- [ ] Validate all numeric parameters (ranges)
- [ ] Add URL reachability check endpoint

**RTSP Validation Pattern:**
```python
RTSP_URL_PATTERN = re.compile(
    r'^rtsps?://'
    r'(?:(?P<user>[^:@]+)(?::(?P<pass>[^@]+))?@)?'  # optional credentials
    r'(?P<host>[a-zA-Z0-9.-]+)'
    r'(?::(?P<port>\d+))?'
    r'(?P<path>/[^\s]*)?$'
)
```

### 2.3 CORS & Security Headers

**Tasks:**
- [ ] Configure CORS for specific origins (env-based)
- [ ] Add security headers middleware (CSP, X-Frame-Options, etc.)
- [ ] Implement HTTPS redirect option
- [ ] Add request ID for tracing

### 2.4 Logging & Monitoring

**Tasks:**
- [ ] Add structured logging with correlation IDs
- [ ] Implement log rotation
- [ ] Add Prometheus metrics endpoint (`/metrics`)
- [ ] Create health check dashboard data
- [ ] Add error alerting hooks (webhook)

**Metrics to Track:**
```
thewallflower_streams_total{status="running|stopped|error"}
thewallflower_frames_processed_total{stream_id}
thewallflower_transcripts_total{stream_id}
thewallflower_whisper_connection_status{stream_id}
thewallflower_ffmpeg_restarts_total{stream_id}
thewallflower_api_requests_total{endpoint, method, status}
```

---

## Phase 3: Core Feature Completion

**Goal:** Complete all planned MVP features.

### 3.1 Transcript Persistence

**Problem:** Transcripts lost on restart, only last 100 in memory.

**Database Schema:**
```python
# models.py
class Transcript(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: int = Field(foreign_key="stream.id", index=True)
    text: str
    start_time: float  # seconds from stream start
    end_time: float
    is_final: bool = Field(default=True)
    confidence: Optional[float] = None
    speaker_id: Optional[int] = Field(default=None, foreign_key="speaker.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

**Tasks:**
- [ ] Add Transcript model
- [ ] Modify worker to persist transcripts
- [ ] Add transcript search endpoint (`GET /api/transcripts?q=`)
- [ ] Add transcript export (JSON, SRT, VTT)
- [ ] Implement transcript retention policy
- [ ] Add transcript pagination to API
- [ ] Update frontend transcript display

### 3.2 Real-time Updates (SSE)

**Problem:** Frontend polls every 2-3 seconds, inefficient.

**Solution:** Server-Sent Events for real-time updates.

```python
# main.py
@app.get("/api/streams/{stream_id}/events")
async def stream_events(stream_id: int):
    """SSE endpoint for real-time stream updates."""
    async def event_generator():
        while True:
            status = manager.get_status(stream_id)
            yield f"event: status\ndata: {json.dumps(status)}\n\n"

            transcripts = manager.get_new_transcripts(stream_id, since=last_id)
            if transcripts:
                yield f"event: transcript\ndata: {json.dumps(transcripts)}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Tasks:**
- [ ] Add SSE endpoint for stream events
- [ ] Add SSE endpoint for global events (new streams, etc.)
- [ ] Update frontend to use EventSource
- [ ] Add reconnection logic in frontend
- [ ] Remove polling from StreamCard

### 3.3 Snapshot Storage & Serving

**Problem:** Snapshots captured but not exposed.

**Tasks:**
- [ ] Store snapshots to disk (configurable path)
- [ ] Add snapshot retention (keep last N or time-based)
- [ ] Add `GET /api/streams/{id}/snapshot` endpoint
- [ ] Add snapshot history endpoint
- [ ] Add thumbnail generation (smaller size)

### 3.4 Video Recording

**Tasks:**
- [ ] Add recording toggle per stream
- [ ] Implement segment-based recording (configurable duration)
- [ ] Add recording storage management
- [ ] Create recording playback endpoint
- [ ] Add recording download option
- [ ] Implement retention policy for recordings

---

## Phase 4: Speaker Diarization

**Goal:** Detect who is speaking and split conversations by speaker.

### 4.1 Overview

Speaker diarization answers "who spoke when" by:
1. Detecting voice activity (VAD)
2. Extracting speaker embeddings
3. Clustering embeddings to identify unique speakers
4. Assigning speaker labels to transcript segments

### 4.2 Technology Options

| Approach | Pros | Cons |
|----------|------|------|
| **pyannote.audio** | State-of-the-art, pre-trained | Heavy (requires GPU ideally), license for commercial |
| **Resemblyzer** | Lightweight embeddings | Need separate clustering |
| **SpeechBrain** | Full toolkit, flexible | Complex setup |
| **WhisperX** | Integrates with Whisper | Additional dependency |
| **Simple VAD + Clustering** | Lightweight, no GPU | Less accurate |

**Recommended:** Start with **Resemblyzer + sklearn clustering** for CPU-friendly approach, upgrade to **pyannote.audio** for accuracy.

### 4.3 Database Schema

```python
# models.py
class Speaker(SQLModel, table=True):
    """Represents a unique speaker detected in streams."""
    id: Optional[int] = Field(default=None, primary_key=True)
    stream_id: int = Field(foreign_key="stream.id", index=True)
    name: Optional[str] = None  # User-assigned name
    embedding: bytes  # Serialized numpy array (speaker voice print)
    color: str = Field(default="#6366f1")  # UI display color
    sample_count: int = Field(default=0)  # Number of segments for this speaker
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SpeakerAlias(SQLModel, table=True):
    """Link speakers across streams (same person, different streams)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str  # Global speaker name
    speaker_ids: str  # JSON array of speaker IDs
```

### 4.4 Architecture

```
Audio Stream
    │
    ▼
┌─────────────────┐
│  Voice Activity │  ← Detect speech segments
│    Detection    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Embedding    │  ← Extract voice fingerprint
│    Extraction   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Clustering   │  ← Group by speaker
│   (Online/Batch)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Speaker Label  │  ← Assign to transcript
│   Assignment    │
└─────────────────┘
```

### 4.5 Implementation Plan

#### Step 1: Add Speaker Embedding Service

```python
# services/speaker_service.py
from resemblyzer import VoiceEncoder, preprocess_wav
import numpy as np
from sklearn.cluster import AgglomerativeClustering

class SpeakerService:
    def __init__(self):
        self.encoder = VoiceEncoder()
        self.embeddings_buffer: dict[int, list] = {}  # stream_id -> embeddings

    def extract_embedding(self, audio_segment: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """Extract speaker embedding from audio segment."""
        wav = preprocess_wav(audio_segment, source_sr=sample_rate)
        return self.encoder.embed_utterance(wav)

    def identify_speaker(self, stream_id: int, embedding: np.ndarray, threshold: float = 0.75) -> int:
        """Match embedding to known speaker or create new one."""
        # Compare with known speakers using cosine similarity
        # Return speaker_id
        pass

    def cluster_speakers(self, stream_id: int, n_speakers: int = None) -> dict:
        """Re-cluster all embeddings for a stream."""
        # Use AgglomerativeClustering
        pass
```

#### Step 2: Integrate with Audio Pipeline

```python
# worker.py modifications
class StreamWorker:
    def __init__(self, ...):
        self.speaker_service = SpeakerService()
        self.audio_buffer = []  # Buffer for speaker detection
        self.buffer_duration = 2.0  # seconds

    def _process_audio_for_diarization(self, audio_chunk: bytes):
        """Process audio chunk for speaker detection."""
        self.audio_buffer.append(audio_chunk)

        # When buffer reaches duration threshold
        if self._buffer_duration() >= self.buffer_duration:
            audio_segment = self._combine_buffer()
            embedding = self.speaker_service.extract_embedding(audio_segment)
            speaker_id = self.speaker_service.identify_speaker(
                self.stream_id, embedding
            )

            # Attach speaker_id to recent transcripts
            self._assign_speaker_to_transcripts(speaker_id)
            self.audio_buffer = []
```

#### Step 3: Add API Endpoints

```python
# main.py additions
@app.get("/api/streams/{stream_id}/speakers")
async def get_speakers(stream_id: int):
    """Get all detected speakers for a stream."""
    pass

@app.patch("/api/speakers/{speaker_id}")
async def update_speaker(speaker_id: int, name: str):
    """Assign a name to a detected speaker."""
    pass

@app.post("/api/speakers/merge")
async def merge_speakers(speaker_ids: list[int], target_name: str):
    """Merge multiple speakers into one (same person)."""
    pass

@app.get("/api/transcripts")
async def get_transcripts(stream_id: int, speaker_id: int = None):
    """Get transcripts, optionally filtered by speaker."""
    pass
```

#### Step 4: Frontend Updates

- Add speaker color coding in transcript display
- Add speaker management panel
- Allow drag-and-drop to merge speakers
- Show speaker timeline visualization
- Add speaker filter in transcript view

### 4.6 Advanced Diarization Features

**Phase 4b - Enhanced Accuracy:**
- [ ] Use pyannote.audio for better accuracy (GPU)
- [ ] Implement speaker overlap detection
- [ ] Add voice activity detection pre-filter
- [ ] Implement online clustering (update without full re-cluster)

**Phase 4c - Speaker Recognition:**
- [ ] Train on known speakers (enrollment)
- [ ] Cross-stream speaker identification
- [ ] Speaker verification (is this person X?)
- [ ] Import speaker profiles

---

## Phase 5: Advanced Features

### 5.1 Face Detection & Recognition

**Tasks:**
- [ ] Implement FaceDetectionProcessor (MTCNN or MediaPipe)
- [ ] Add face embedding extraction
- [ ] Link faces to speakers (multi-modal identity)
- [ ] Add face recognition (optional)
- [ ] Privacy controls (blur faces option)

### 5.2 Search & Analytics

**Tasks:**
- [ ] Full-text search on transcripts
- [ ] Speaker activity analytics
- [ ] Word frequency / word cloud
- [ ] Conversation sentiment analysis
- [ ] Activity heatmaps (when was speech detected)

### 5.3 Notifications & Alerts

**Tasks:**
- [ ] Keyword detection alerts
- [ ] Speaker detection alerts (notify when person X speaks)
- [ ] Silence alerts (no speech for N minutes)
- [ ] Webhook integrations
- [ ] Email/push notifications

### 5.4 Multi-Language Support

**Tasks:**
- [ ] Language detection per stream
- [ ] WhisperLive language configuration
- [ ] Translation option (transcribe + translate)
- [ ] UI localization

---

## Technical Specifications

### Speaker Diarization Requirements

**Minimum Hardware:**
- CPU: 4 cores
- RAM: 8GB (16GB recommended)
- Storage: 10GB + recordings

**With GPU (recommended for pyannote):**
- NVIDIA GPU with 4GB+ VRAM
- CUDA 11.x

**Dependencies:**
```txt
# requirements.txt additions
resemblyzer>=0.1.3
webrtcvad>=2.0.10
scikit-learn>=1.3.0
numpy>=1.24.0

# Optional for better accuracy
pyannote.audio>=3.1.0  # Requires GPU
speechbrain>=0.5.0
```

### Database Migrations

**Tool:** Alembic

**Setup:**
```bash
alembic init alembic
alembic revision --autogenerate -m "Add speakers and transcripts"
alembic upgrade head
```

### API Rate Limits

| Endpoint | Rate Limit |
|----------|------------|
| POST /api/streams | 10/minute |
| GET /api/transcripts | 60/minute |
| GET /api/video/* | 30/minute |
| POST /api/auth/* | 5/minute |

---

## Architecture Evolution

### Current (v0.1)
```
┌──────────┐     ┌──────────┐     ┌─────────────┐
│ Frontend │────▶│ Backend  │────▶│ WhisperLive │
└──────────┘     └────┬─────┘     └─────────────┘
                      │
                 ┌────▼────┐
                 │ SQLite  │
                 └─────────┘
```

### Target (v1.0)
```
┌──────────┐     ┌──────────────────────────────────┐
│ Frontend │────▶│            Backend               │
└──────────┘     │  ┌─────────┐  ┌───────────────┐  │
                 │  │ FastAPI │  │ Stream Manager│  │
                 │  └────┬────┘  └───────┬───────┘  │
                 │       │               │          │
                 │  ┌────▼────┐   ┌──────▼───────┐  │
                 │  │   Auth  │   │    Workers   │  │
                 │  └─────────┘   │ ┌──────────┐ │  │
                 │                │ │  Video   │ │  │
                 │                │ ├──────────┤ │  │
                 │                │ │  Audio   │ │  │
                 │                │ ├──────────┤ │  │
                 │                │ │ Speaker  │ │  │
                 │                │ │Diarizer  │ │  │
                 │                │ └──────────┘ │  │
                 │                └──────┬───────┘  │
                 └───────────────────────┼─────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 │                       │                       │
           ┌─────▼─────┐          ┌──────▼──────┐         ┌──────▼──────┐
           │  SQLite/  │          │ WhisperLive │         │   Storage   │
           │  Postgres │          │    (GPU)    │         │ (Snapshots, │
           └───────────┘          └─────────────┘         │ Recordings) │
                                                          └─────────────┘
```

---

## Phase 6: Intel GPU & OpenVINO Support

**Goal:** Enable hardware acceleration on Intel GPUs and CPUs using OpenVINO.

### 6.1 Overview

Intel's OpenVINO toolkit provides optimized inference for:
- Intel CPUs (with AVX-512, VNNI)
- Intel integrated GPUs (Gen 9+, Xe, Arc)
- Intel VPUs (Movidius, dedicated AI accelerators)
- Intel discrete GPUs (Arc A-series)

### 6.2 WhisperLive Backend Options

| Backend | Hardware | Performance | Complexity |
|---------|----------|-------------|------------|
| **CPU (default)** | Any CPU | Baseline | Simple |
| **CUDA** | NVIDIA GPU | 5-10x faster | Medium |
| **OpenVINO** | Intel CPU/GPU | 2-5x faster | Medium |
| **ROCm** | AMD GPU | 3-8x faster | Complex |

### 6.3 Docker Image Strategy

**Approach:** Multiple tagged images for different acceleration backends.

```yaml
# docker-compose.yml - Image selection via environment
services:
  whisper-live:
    image: ${WHISPER_IMAGE:-ghcr.io/collabora/whisperlive-cpu:latest}
    # Official Collabora images:
    # - ghcr.io/collabora/whisperlive-cpu:latest      (CPU only)
    # - ghcr.io/collabora/whisperlive-gpu:latest      (NVIDIA CUDA)
    # - ghcr.io/collabora/whisperlive-openvino:latest (Intel OpenVINO)
```

**Environment Variables:**
```bash
# .env file examples

# Default (CPU)
WHISPER_IMAGE=ghcr.io/collabora/whisperlive-cpu:latest

# NVIDIA GPU
WHISPER_IMAGE=ghcr.io/collabora/whisperlive-gpu:latest

# Intel GPU/CPU with OpenVINO (official Collabora image)
WHISPER_IMAGE=ghcr.io/collabora/whisperlive-openvino:latest
```

### 6.4 Official OpenVINO Image

Collabora provides an official OpenVINO-enabled WhisperLive image:

```bash
# Pull the official OpenVINO image
docker pull ghcr.io/collabora/whisperlive-openvino:latest

# Run with Intel GPU passthrough
docker run -it --device=/dev/dri -p 9090:9090 ghcr.io/collabora/whisperlive-openvino:latest
```

**Note:** Running WhisperLive with OpenVINO inside Docker automatically enables GPU support (iGPU/dGPU) without requiring additional host setup. The first run may be slow as OpenVINO compiles the model to a device-specific blob, which is cached for subsequent runs.

### 6.5 Device Auto-Detection

**Implementation:**
```python
# utils/hardware_detect.py
import subprocess
import os

def detect_acceleration():
    """Detect available hardware acceleration."""

    # Check for NVIDIA GPU
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True)
        if result.returncode == 0:
            return 'cuda', 'NVIDIA GPU detected'
    except FileNotFoundError:
        pass

    # Check for Intel GPU
    try:
        result = subprocess.run(['ls', '/dev/dri'], capture_output=True)
        if b'renderD128' in result.stdout:
            # Check if it's Intel
            lspci = subprocess.run(['lspci'], capture_output=True)
            if b'Intel' in lspci.stdout and b'VGA' in lspci.stdout:
                return 'openvino', 'Intel GPU detected'
    except FileNotFoundError:
        pass

    # Check for Intel CPU features
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'avx512' in cpuinfo.lower() or 'vnni' in cpuinfo.lower():
                return 'openvino-cpu', 'Intel CPU with AVX-512/VNNI detected'
    except FileNotFoundError:
        pass

    return 'cpu', 'No acceleration detected, using CPU'

def get_recommended_image():
    """Get recommended Docker image based on hardware."""
    accel, reason = detect_acceleration()

    images = {
        'cuda': 'ghcr.io/collabora/whisperlive-gpu:latest',
        'openvino': 'ghcr.io/collabora/whisperlive-openvino:latest',
        'openvino-cpu': 'ghcr.io/collabora/whisperlive-openvino:latest',
        'cpu': 'ghcr.io/collabora/whisperlive-cpu:latest',
    }

    return images[accel], reason
```

### 6.6 Docker Compose with Auto-Selection

**docker-compose.yml:**
```yaml
services:
  whisper-live:
    image: ${WHISPER_IMAGE:-ghcr.io/collabora/whisperlive:latest}
    container_name: whisper-live
    environment:
      - WHISPER_MODEL=${WHISPER_MODEL:-base.en}
      - OPENVINO_DEVICE=${OPENVINO_DEVICE:-AUTO}
    devices:
      # Intel GPU passthrough
      - /dev/dri:/dev/dri
    group_add:
      - video
      - render
    # For NVIDIA (uncomment if using CUDA image)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]
```

### 6.7 Intel GPU Device Passthrough

**Required for Intel iGPU/dGPU:**
```yaml
services:
  whisper-live:
    devices:
      - /dev/dri:/dev/dri        # GPU device
    group_add:
      - video                     # Access to /dev/dri
      - render                    # For newer kernels
    environment:
      - OPENVINO_DEVICE=GPU       # Use GPU
      # Or AUTO for automatic selection
```

**Host Requirements:**
```bash
# Install Intel compute runtime
sudo apt install -y intel-opencl-icd intel-level-zero-gpu

# Add user to video/render groups
sudo usermod -aG video,render $USER

# Verify GPU is accessible
ls -la /dev/dri/
# Should show renderD128
```

### 6.8 OpenVINO Model Optimization

**Whisper Model Conversion:**
```python
# scripts/convert_whisper_openvino.py
from openvino import convert_model, save_model
from transformers import WhisperForConditionalGeneration

def convert_whisper_to_openvino(model_name: str = "openai/whisper-base.en"):
    """Convert Whisper model to OpenVINO IR format."""

    # Load HuggingFace model
    model = WhisperForConditionalGeneration.from_pretrained(model_name)

    # Convert to OpenVINO
    ov_model = convert_model(model)

    # Apply optimizations
    from openvino.runtime import Core
    core = Core()

    # Compress to INT8 for faster inference
    from openvino.tools import mo
    compressed_model = mo.compress_model(ov_model, compress_to_fp16=True)

    # Save
    save_model(compressed_model, f"whisper_openvino/{model_name.split('/')[-1]}.xml")

    return compressed_model
```

### 6.9 Implementation Tasks

#### Phase 6a: Basic OpenVINO Support
- [ ] Create OpenVINO WhisperLive Docker image
- [ ] Test on Intel integrated GPU (common in NUCs, mini PCs)
- [ ] Document Intel GPU passthrough for Docker
- [ ] Add `WHISPER_IMAGE` environment variable to compose
- [ ] Update README with hardware options

#### Phase 6b: Auto-Detection
- [ ] Implement hardware detection script
- [ ] Add CLI command: `thewallflower detect-hardware`
- [ ] Generate `.env` file with recommended settings
- [ ] Add hardware info to `/api/system/info` endpoint

#### Phase 6c: Model Optimization
- [ ] Convert Whisper models to OpenVINO IR format
- [ ] Test INT8 quantization for speed
- [ ] Benchmark CPU vs iGPU vs dGPU
- [ ] Publish optimized models

#### Phase 6d: Multi-Backend Support
- [ ] Abstract backend selection in code
- [ ] Support runtime backend switching
- [ ] Add fallback chain (GPU → CPU)
- [ ] Implement health checks per backend

### 6.10 Performance Expectations

| Hardware | Model | Real-time Factor | Notes |
|----------|-------|------------------|-------|
| Intel i5 CPU | base.en | ~0.5x | May struggle with real-time |
| Intel i7 (AVX-512) | base.en | ~1.2x | Adequate for real-time |
| Intel iGPU (UHD 630) | base.en | ~2x | Good for real-time |
| Intel Arc A380 | base.en | ~5x | Excellent |
| Intel Arc A770 | base.en | ~8x | Near NVIDIA performance |

*Real-time factor: 1x = processes audio as fast as it plays*

### 6.11 Dockerfile Variants

**Create multiple Dockerfiles:**
```
docker/
├── Dockerfile              # Base (CPU only)
├── Dockerfile.cuda         # NVIDIA GPU
├── Dockerfile.openvino     # Intel GPU/CPU
└── Dockerfile.rocm         # AMD GPU (future)
```

**GitHub Actions for multi-arch builds:**
```yaml
# .github/workflows/docker-build.yml
jobs:
  build:
    strategy:
      matrix:
        variant: [cpu, cuda, openvino]
    steps:
      - uses: docker/build-push-action@v5
        with:
          file: docker/Dockerfile.${{ matrix.variant }}
          tags: ghcr.io/jellman86/thewallflower-${{ matrix.variant }}:latest
```

---

## Implementation Priority

### Immediate (Week 1-2)
1. FFmpeg stderr handling
2. WhisperLive reconnection improvements
3. Transcript persistence
4. Basic input validation

### Short-term (Week 3-4)
1. SSE for real-time updates
2. Authentication (basic)
3. Snapshot serving
4. Structured logging

### Medium-term (Month 2)
1. Speaker diarization (basic)
2. Full authentication + permissions
3. Transcript search
4. Recording support

### Long-term (Month 3+)
1. Advanced speaker diarization
2. Face detection
3. Analytics dashboard
4. Multi-language support

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Stream uptime | 99.9% |
| Transcript accuracy | >90% (WhisperLive dependent) |
| Speaker diarization accuracy | >85% |
| API response time (p95) | <200ms |
| Frontend load time | <2s |
| Memory usage per stream | <500MB |

---

## References

- [WhisperLive Documentation](https://github.com/collabora/WhisperLive)
- [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- [Resemblyzer](https://github.com/resemble-ai/Resemblyzer)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Svelte 5 Runes](https://svelte.dev/docs/svelte/what-are-runes)

---

*This document should be updated as development progresses.*

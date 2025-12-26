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
7. [Technical Specifications](#technical-specifications)
8. [Architecture Evolution](#architecture-evolution)

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

# TheWallflower Development Plan v2.0

## Priority: ROBUSTNESS FIRST

**Last Updated:** December 27, 2025
**Status:** Post-Code Review
**Overall Risk Level:** HIGH (requires immediate attention)

---

## Executive Summary

A comprehensive code review identified **4 critical**, **12 high**, and **20+ medium** severity issues across the codebase. This updated development plan prioritizes robustness and stability over new features.

### Current State
- MVP: ~75% complete
- Robustness: ~40% (significant gaps)
- Security: ~30% (critical issues)
- Production Ready: NO

---

## Critical Issues Requiring Immediate Fix

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | Missing `json` import | main.py:799 | Runtime crash on SSE |
| 2 | CORS allows all origins + credentials | main.py:65-71 | Security vulnerability |
| 3 | Race condition in StreamStatus | worker.py:156-167 | Data corruption |
| 4 | FFmpeg zombie process risk | worker.py:499-559 | Resource exhaustion |

---

## Phase 0: Critical Hotfixes (Immediate - 1 Day)

### 0.1 Fix Missing Import
```python
# main.py - Add to imports
import json
```

### 0.2 Fix CORS Security
```python
# main.py:65-71 - Replace wildcard CORS
import os
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

### 0.3 Add Thread Safety to StreamStatus
```python
# worker.py - Add status lock
class StreamWorker:
    def __init__(self, ...):
        self._status_lock = threading.Lock()

    def _update_status(self, **kwargs):
        with self._status_lock:
            for key, value in kwargs.items():
                setattr(self._status, key, value)

    @property
    def status(self) -> StreamStatus:
        with self._status_lock:
            if self._mjpeg_streamer:
                self._status.fps = self._mjpeg_streamer.fps
            return copy.copy(self._status)  # Return copy to prevent races
```

### 0.4 Fix FFmpeg Process Cleanup
```python
# worker.py - Atomic process cleanup
def _cleanup_ffmpeg(self, process: subprocess.Popen, timeout: int = 5):
    if process is None:
        return
    try:
        # Close pipes first
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        # Terminate gracefully
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)  # Final timeout
    except Exception as e:
        logger.error(f"FFmpeg cleanup error: {e}")
```

---

## Phase 1: Backend Robustness (Week 1-2)

### 1.1 Thread Safety & Concurrency

**Priority:** CRITICAL

| Task | File | Effort |
|------|------|--------|
| Add locks to all StreamStatus updates | worker.py | 2h |
| Fix thread resurrection race conditions | stream_manager.py | 3h |
| Add lock to transcript batch processing | transcript_service.py | 1h |
| Fix event broadcaster async/sync mixing | event_broadcaster.py | 2h |
| Replace asyncio.Event with threading.Event | processors.py | 1h |

**Implementation Pattern:**
```python
# Use RLock for nested acquisitions
self._status_lock = threading.RLock()

# Always use context manager
with self._status_lock:
    self._status.video_connected = True
    self._emit_status_event()
```

### 1.2 Resource Management

**Priority:** HIGH

| Task | File | Effort |
|------|------|--------|
| Add frame read timeout wrapper | worker.py | 2h |
| Implement proper resource cleanup in finally blocks | worker.py | 2h |
| Add FFmpeg process monitoring | worker.py | 2h |
| Handle SSE client disconnection gracefully | main.py | 1h |
| Add OpenCV VideoCapture timeout enforcement | worker.py | 2h |

**Frame Read Timeout Implementation:**
```python
import concurrent.futures

def _read_frame_with_timeout(self, cap, timeout=5.0):
    """Read frame with timeout protection."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(cap.read)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning(f"Frame read timeout after {timeout}s")
            return False, None
```

### 1.3 Error Handling Improvements

**Priority:** HIGH

| Task | File | Effort |
|------|------|--------|
| Replace broad Exception catches with specific types | Multiple | 3h |
| Add error categorization enum | worker.py | 1h |
| Implement error history tracking | worker.py | 2h |
| Add structured error responses | main.py | 2h |
| Surface file write errors to API | worker.py | 1h |

**Error Categorization:**
```python
class StreamError(str, Enum):
    CONNECTION_REFUSED = "connection_refused"
    AUTH_FAILED = "auth_failed"
    TIMEOUT = "timeout"
    CODEC_ERROR = "codec_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERNAL_ERROR = "internal_error"
```

### 1.4 Health Monitoring Enhancements

**Priority:** MEDIUM

| Task | File | Effort |
|------|------|--------|
| Add degraded health check responses | main.py | 1h |
| Implement thread watchdog with metrics | stream_manager.py | 2h |
| Add database connectivity check | main.py | 1h |
| Add WhisperLive connectivity check | main.py | 1h |
| Expose metrics endpoint (/metrics) | main.py | 3h |

**Enhanced Health Check:**
```python
@app.get("/api/health")
def health_check():
    issues = []
    status = "healthy"

    # Check database
    try:
        with Session(engine) as session:
            session.exec(select(StreamConfig).limit(1))
    except Exception as e:
        issues.append(f"Database: {e}")
        status = "degraded"

    # Check streams
    workers = stream_manager.get_all_workers()
    failed_streams = [
        sid for sid, w in workers.items()
        if w.status.circuit_breaker_state == CircuitBreakerState.OPEN
    ]
    if failed_streams:
        issues.append(f"Failed streams: {failed_streams}")
        status = "degraded"

    if status == "degraded":
        raise HTTPException(status_code=503, detail={"status": status, "issues": issues})

    return {"status": status, "streams_active": len(workers)}
```

---

## Phase 2: Frontend Robustness (Week 2-3)

### 2.1 Memory Leak Fixes

**Priority:** CRITICAL

| Task | File | Effort |
|------|------|--------|
| Fix SSE connection leak in TranscriptPanel | TranscriptPanel.svelte | 1h |
| Add imageRetryTimeout cleanup | StreamCard.svelte | 30m |
| Add AbortController to all API calls | api.js | 2h |
| Fix SSE reconnection in TranscriptPanel | TranscriptPanel.svelte | 1h |
| Add cleanup effects to App.svelte | App.svelte | 1h |

**AbortController Implementation:**
```javascript
// api.js
export const streams = {
  async list(signal) {
    const response = await fetch(`${BASE_URL}/streams`, { signal });
    return handleResponse(response);
  },
};

// Component usage
$effect(() => {
  const controller = new AbortController();
  loadStreams(controller.signal);
  return () => controller.abort();
});
```

### 2.2 Error Handling & UX

**Priority:** HIGH

| Task | File | Effort |
|------|------|--------|
| Add error state to StatsPanel | StatsPanel.svelte | 1h |
| Implement retry logic in api.js | api.js | 2h |
| Add structured error types | api.js | 1h |
| Show SSE errors in TranscriptPanel | TranscriptPanel.svelte | 1h |
| Add loading progress indicators | SettingsModal.svelte | 1h |

**Retry Logic:**
```javascript
async function fetchWithRetry(url, options = {}, maxRetries = 3) {
  let lastError;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(url, options);
      return await handleResponse(response);
    } catch (e) {
      lastError = e;
      if (i < maxRetries - 1) {
        await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
      }
    }
  }
  throw lastError;
}
```

### 2.3 Accessibility Fixes

**Priority:** MEDIUM

| Task | File | Effort |
|------|------|--------|
| Add aria-labels to icon buttons | App.svelte, StreamCard.svelte | 1h |
| Implement focus trap in modal | SettingsModal.svelte | 2h |
| Add form validation ARIA attributes | SettingsModal.svelte | 1h |
| Fix color contrast for muted text | app.css | 30m |
| Add aria-live regions for loading states | Multiple | 1h |

---

## Phase 3: Database & Security (Week 3-4)

### 3.1 Database Improvements

**Priority:** HIGH

| Task | File | Effort |
|------|------|--------|
| Enable SQLite foreign key enforcement | db.py | 30m |
| Add proper transaction handling | main.py | 2h |
| Consider PostgreSQL migration | db.py, docker-compose.yml | 4h |
| Fix transcript cleanup race condition | transcript_service.py | 1h |
| Add connection pooling | db.py | 2h |

**Foreign Key Enforcement:**
```python
# db.py
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

### 3.2 Security Hardening

**Priority:** HIGH

| Task | File | Effort |
|------|------|--------|
| Add authentication to debug endpoints | routers/debug.py | 2h |
| Validate numeric query parameters | main.py | 1h |
| Add export format enum validation | main.py | 30m |
| Sanitize RTSP URL before FFmpeg | worker.py | 1h |
| Add security headers middleware | main.py | 1h |
| Rate limit API endpoints | main.py | 2h |

**Input Validation:**
```python
from fastapi import Query
from enum import Enum

class ExportFormat(str, Enum):
    JSON = "json"
    TXT = "txt"
    SRT = "srt"
    VTT = "vtt"

@app.get("/api/transcripts/export")
def export_transcripts(
    stream_id: int,
    format: ExportFormat = ExportFormat.JSON,
    limit: int = Query(default=1000, le=10000, ge=1),
):
    ...
```

### 3.3 Configuration Management

**Priority:** MEDIUM

| Task | File | Effort |
|------|------|--------|
| Move hardcoded values to config | config.py | 2h |
| Add environment variable documentation | README.md | 1h |
| Validate configuration on startup | config.py | 1h |
| Add configuration reload endpoint | main.py | 2h |

---

## Phase 4: Testing & Observability (Week 4-5)

### 4.1 Test Coverage

**Priority:** HIGH

| Task | Effort |
|------|--------|
| Unit tests for stream_validator.py | 3h |
| Unit tests for worker.py (mocked) | 4h |
| Integration tests for API endpoints | 4h |
| SSE event stream tests | 2h |
| Concurrency tests (thread sanitizer) | 3h |

### 4.2 Observability

**Priority:** MEDIUM

| Task | File | Effort |
|------|------|--------|
| Add Prometheus metrics endpoint | main.py | 3h |
| Implement structured logging | Multiple | 2h |
| Add request ID tracing | main.py | 1h |
| Create Grafana dashboard template | docs/ | 2h |

**Metrics to Track:**
- `streams_total` (gauge)
- `stream_fps` (gauge per stream)
- `transcripts_total` (counter)
- `api_requests_total` (counter by endpoint)
- `api_request_duration_seconds` (histogram)
- `ffmpeg_restarts_total` (counter)
- `circuit_breaker_state` (gauge per stream)

---

## Phase 5: Feature Completion (Week 5-8)

### 5.1 Authentication (Deferred from MVP)

| Task | Effort |
|------|--------|
| JWT authentication implementation | 4h |
| User model and password hashing | 2h |
| Login/logout endpoints | 2h |
| Protected route middleware | 2h |
| Frontend auth integration | 4h |

### 5.2 Recording Feature

| Task | Effort |
|------|--------|
| Recording processor implementation | 4h |
| Segment-based file management | 3h |
| Recording API endpoints | 2h |
| Retention policy | 2h |
| Frontend recording controls | 3h |

### 5.3 Speaker Diarization

| Task | Effort |
|------|--------|
| Voice embedding extraction | 4h |
| Speaker clustering algorithm | 4h |
| Speaker database models | 2h |
| Speaker API endpoints | 2h |
| Frontend speaker visualization | 4h |

---

## Implementation Priority Matrix

```
                    IMPACT
                    High    Medium    Low
              +--------+--------+--------+
         High |  P0    |   P1   |   P2   |
URGENCY       +--------+--------+--------+
       Medium |  P1    |   P2   |   P3   |
              +--------+--------+--------+
          Low |  P2    |   P3   |   P4   |
              +--------+--------+--------+
```

### P0 (Do Now - This Week)
1. Fix missing json import
2. Fix CORS security
3. Add StreamStatus thread safety
4. Fix FFmpeg zombie processes
5. Fix frontend SSE memory leaks

### P1 (Next Week)
1. Add frame read timeout
2. Fix thread resurrection races
3. Add AbortController to frontend
4. Enable SQLite foreign keys
5. Add authentication to debug routes

### P2 (Week 3-4)
1. Replace broad exception catches
2. Add retry logic to frontend
3. Implement health check degradation
4. Add accessibility fixes
5. Add input validation

### P3 (Month 2)
1. Add Prometheus metrics
2. Write unit tests
3. Add structured logging
4. PostgreSQL migration consideration

### P4 (Future)
1. Speaker diarization
2. Recording feature
3. Face detection
4. Multi-language support

---

## Success Metrics

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Critical bugs | 4 | 0 | Week 1 |
| High bugs | 12 | 0 | Week 2 |
| Test coverage | 0% | 60% | Week 5 |
| Uptime (24h test) | Unknown | 99% | Week 3 |
| Memory growth (24h) | Unknown | <10% | Week 3 |
| WCAG AA compliance | ~50% | 100% | Week 4 |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SQLite write corruption | Medium | High | Migrate to PostgreSQL |
| Thread deadlock | Low | Critical | Add lock ordering, timeouts |
| Memory exhaustion | Medium | High | Add resource limits, monitoring |
| FFmpeg hangs | Medium | Medium | Process timeout, watchdog |
| WhisperLive unavailable | Medium | Medium | Circuit breaker, graceful degradation |

---

## Next Steps

1. **Immediately**: Apply Phase 0 hotfixes
2. **This Week**: Complete Phase 1.1 (thread safety)
3. **Next Week**: Complete Phase 1.2-1.3 (resource management, error handling)
4. **Week 3**: Complete Phase 2 (frontend robustness)
5. **Week 4**: Complete Phase 3 (database, security)

---

## Appendix: Files Requiring Changes

### Critical (Phase 0-1)
- `backend/app/main.py` - Import fix, CORS, health check
- `backend/app/worker.py` - Thread safety, timeouts, cleanup
- `backend/app/stream_manager.py` - Thread resurrection fix
- `backend/app/processors.py` - Replace asyncio.Event
- `backend/app/services/event_broadcaster.py` - Async/sync fix
- `backend/app/services/transcript_service.py` - Batch lock

### High Priority (Phase 2-3)
- `frontend/src/lib/services/api.js` - AbortController, retry
- `frontend/src/lib/components/TranscriptPanel.svelte` - SSE fix
- `frontend/src/lib/components/StreamCard.svelte` - Cleanup fix
- `frontend/src/lib/components/SettingsModal.svelte` - A11Y
- `backend/app/db.py` - Foreign keys, pooling
- `backend/app/routers/debug.py` - Authentication

### Medium Priority (Phase 4-5)
- `backend/app/config.py` - Configuration management
- `tests/` - New test files
- `docs/` - Updated documentation

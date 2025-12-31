# TheWallflower Development Plan v2.0 (Updated Dec 31, 2025)

## Priority: STABILIZATION COMPLETED

**Last Updated:** December 31, 2025
**Overall Status:** Phase 0 & 1 Substantially Complete

---

## Resolved Critical Issues

| # | Issue | Location | Status |
|---|-------|----------|--------|
| 1 | Missing `json` import | main.py | ✅ FIXED |
| 2 | CORS security | main.py | ✅ FIXED |
| 3 | Race condition in StreamStatus | worker.py | ✅ FIXED |
| 4 | FFmpeg zombie process risk | worker.py | ✅ FIXED |
| 5 | Transcription failure (Audio filters) | worker.py | ✅ FIXED |
| 6 | SSE Connection interruptions | main.py | ✅ FIXED |

---

## Phase 0: System Stabilization (COMPLETED)

### 0.1 Backend Core
- ✅ Fixed missing imports and JSON parsing.
- ✅ Implemented thread-safe status updates in `worker.py`.
- ✅ Standardized go2rtc client communication.
- ✅ Optimized FFmpeg audio extraction (removed problematic filters).

### 0.2 Network & Signaling
- ✅ Reduced SSE keepalive to 5s for reverse proxy compatibility.
- ✅ Implemented WebRTC signaling proxy via go2rtc.
- ✅ Added support for both `text` and `segments` message formats from AI.

---

## Phase 1: Robustness Enhancements (IN PROGRESS)

### 1.1 Resource Management
- [ ] Add explicit frame read timeouts (OpenCV legacy fallback).
- [ ] Implement deeper FFmpeg process monitoring.
- [ ] Add circuit breaker metrics to health check.

### 1.2 Error Handling
- [ ] structured error responses for all API endpoints.
- [ ] Surface specific FFmpeg errors to the UI (e.g., Auth vs Connection).

---

## Phase 2: Frontend Polishing (Week 1, Jan 2026)

### 2.1 Memory & Lifecycle
- [ ] Verify SSE connection cleanup in `App.svelte`.
- [ ] Add AbortController to all Svelte service calls.

### 2.2 UI Improvements
- [ ] Add transcript auto-scroll toggle.
- [ ] Implement manual "Force Refresh" for WebRTC player.
- [ ] Show VAD status in UI (Silent vs Speaking).

---

## Phase 3: Future Roadmap

1. **Recording & Playback**: Integrate go2rtc recording capabilities.
2. **Speaker Identification**: Basic diarization support.
3. **Model Management**: Dynamic model selection (Base/Small/Medium).
4. **Auth Layer**: JWT-based authentication for the dashboard.
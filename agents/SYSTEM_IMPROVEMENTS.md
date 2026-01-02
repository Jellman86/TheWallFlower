# TheWallflower: Codebase Review & Future Priorities
**Date:** 2026-01-02
**Status:** Post-Initial-Fixes Review

---

## 1. Executive Summary
TheWallflower is a well-architected, modern NVR system focused on privacy and local processing. The integration of `go2rtc` for video handling and `WhisperLive` for audio transcription provides a high-performance foundation. Recent fixes have resolved critical issues with face thumbnail saving and audio histogram reliability.

## 2. Current Codebase State

### Strengths
- **Hybrid Architecture:** Offloading protocol conversion and video streaming to `go2rtc` (written in Go) significantly reduces CPU overhead in the Python backend and eliminates common browser-side video decoding issues.
- **Modern Tech Stack:** 
    - **Backend:** FastAPI, SQLModel (SQLAlchemy 2.0 style), and Pydantic v2.
    - **Frontend:** Svelte 5 with runes, providing a highly reactive and performant UI.
    - **Audio:** Aggressive anti-hallucination tuning for Faster Whisper.
- **Modular Design:** Clear separation between workers (background threads), services (business logic), and routers (API endpoints).

### Recent Improvements (Applied)
- **Dynamic Data Paths:** Fixed hardcoded `/data` paths to allow the system to run in environments without a root `/data` volume (e.g., local dev).
- **Thread Safety:** Fixed a race condition/crash in `worker.py` where background threads were pushing to `asyncio` queues incorrectly.
- **Robustness:** Added error checking to image saving operations to prevent broken database records.

---

## 3. Identified Issues & Technical Debt

### High Priority
- **Face Recognition Limitations:** Currently, the system uses a single embedding per face. This leads to poor recognition when lighting, angles, or distance vary.
- **Recording UX:** Recordings are presented as a list of 15-minute MP4 clips. Navigating 24 hours of video is cumbersome.
- **Status Consistency:** In `worker.py`, many updates to the `_status` object occur outside of the `_status_lock`. While Python's GIL often protects against crashes here, it can lead to inconsistent state visibility in the UI.

### Medium Priority
- **Dead Code:** `processors.py` is currently unused dead code. The original design for a Python-based frame pipeline was superseded by the `go2rtc` integration.
- **Sync Health Checks:** The health monitor in `stream_manager.py` is a synchronous thread checking state, but it lacks an async health check for the `go2rtc` service itself.
- **Incomplete Signal Handling:** While signal handlers exist, they don't explicitly ensure that all child `ffmpeg` processes are reaped if the parent process crashes or is killed aggressively.

### Low Priority
- **Hardcoded Model Paths:** InsightFace models are downloaded to a hardcoded `~/.insightface` path. This should be configurable to a shared data volume to avoid re-downloads on container rebuilds.
- **Manual Migration Repair:** The `docker-entrypoint.sh` contains some manual SQL repair logic that should ideally be handled purely by Alembic migrations.

---

## 4. Prioritized Roadmap

### Phase 1: Face Recognition Upgrade (COMPLETE)
- [x] **Multi-Embedding Support:** Update `Face` model to store multiple embeddings per identity.
- [x] **Training UI:** Create a "Training" or "Library" view where users can upload high-quality photos to pre-train identities (Frigate-style).
- [x] **Quality Filtering:** Only save new embeddings from the camera if they exceed a "quality" threshold (e.g., face size, sharpness).

### Phase 2: Visual Timeline (PENDING)
- [ ] **HLS Concatenation:** Generate dynamic HLS playlists that stitch 15-minute segments into a continuous stream for the UI.
- [ ] **Timeline Scrubber:** Implement a visual timeline in Svelte that shows "speech events", "face detections", and "motion" on a 24-hour bar.

### Phase 3: Technical Cleanup (IN PROGRESS)
- [x] **Thread Audit:** Refactor `worker.py` to use `_update_status` helper exclusively for all state changes.
- [x] **Remove Dead Code:** Delete `processors.py` and remove associated boilerplate.
- [ ] **Async Health Checks:** Implement proper async monitoring of `go2rtc` stream health.

---

## 5. Security Note
The system currently has no authentication layer. It is intended for local network use, but if exposed via reverse proxy, **must** be protected by an external auth provider (Authelia, Authentik) or basic auth at the proxy level.
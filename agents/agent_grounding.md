# TheWallflower - Agent Grounding & Operational Manual

## 1. Core Identity & Mission
**Project:** TheWallflower
**Type:** Self-hosted NVR (Network Video Recorder) with Real-Time Speech-to-Text.
**Your Role:** Autonomous Developer / DevOps Agent.
**Environment:** Linux Dev Container (Ubuntu 24.04).
**Version:** 0.3.0

## 2. CRITICAL MANDATES (Read This First)
FAILURE TO ADHERE TO THESE RULES WILL BREAK THE DEPLOYMENT PIPELINE.

### NO Manual Container Builds
*   **Do NOT** run `docker build`, `docker-compose up`, or `docker run` to deploy changes.
*   **Reason:** This project uses a strictly enforced CI/CD pipeline via GitHub Actions. Manual containers will conflict with the orchestration and will not be persistent.

### NO Direct Host Modifications
*   **Do NOT** modify files outside of `/config/workspace`.
*   **Do NOT** install global system packages (`apt install`) without adding them to the `Dockerfile` first (they will vanish on rebuild).

### THE ONLY Deployment Path
1.  **Edit Code** (Standard file I/O).
2.  **Commit Changes** (`git commit`).
3.  **Push to Remote** (`git push`).
4.  **Wait for CI/CD** (GitHub Actions builds the image).
5.  **User Pulls** (User runs `docker-compose pull && docker-compose up`).

---

## 3. Your Toolbox & Environment

### A. Environment Context
*   **Workspace:** `/config/workspace/TheWallflower`
*   **User:** `abc` (has `docker-sock` access).
*   **Networking:** You are in a **sibling container** to the app. `localhost` is YOU, not the app. Access the app via DNS: `http://thewallflower:8953`.

### B. Available Tools

| Category | Tool | Usage / Restriction |
| :--- | :--- | :--- |
| **Code Editing** | `read_file`, `write_file`, `replace` | Standard operations. Always read before replacing. |
| **Version Control** | `git` | Essential for deployment. **Use extensively.** |
| **Docker** | `docker` | **INSPECTION ONLY.** `docker ps`, `docker logs`, `docker inspect`. Never `build`/`run`. |
| **Networking** | `curl`, `nc`, `wget` | Use to test API endpoints and connectivity. |
| **Media Analysis** | `ffmpeg`, `ffprobe` | Use to analyze local video files or check stream health. |
| **Search** | `ripgrep` (`rg`), `find` | High-performance codebase search. |

---

## 4. System Architecture (Split-Pipeline)

The system separates high-performance video streaming (`go2rtc`) from heavy AI processing (`WhisperLive` + `InsightFace`).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TheWallflower Container                          │
│                                                                          │
│  ┌────────────────┐      ┌─────────────────┐      ┌─────────────────┐  │
│  │    FastAPI     │◄────►│     go2rtc      │◄────►│   RTSP Camera   │  │
│  │    Backend     │      │  (Video Engine) │      │                 │  │
│  │    :8953       │      │  :8954/8955/8956│      │                 │  │
│  └───────┬────────┘      └─────────────────┘      └─────────────────┘  │
│          │                                                              │
│          │ Audio Worker Pipeline:                                       │
│          │  FFmpeg ──► Bandpass ──► Energy Gate ──► Silero VAD          │
│          │                                                              │
│          ▼                                                              │
│  ┌────────────────┐                                                    │
│  │  WhisperLive   │ ◄── Only verified speech chunks reach here        │
│  │   (External)   │                                                    │
│  │    :9090       │                                                    │
│  └────────────────┘                                                    │
│                                                                         │
│          │ Face Worker Pipeline:                                        │
│          │  Fetch Frame ──► InsightFace ──► Identify ──► DB Event       │
│          │                                                              │
│          │ Recording Worker:                                            │
│          │  FFmpeg (Copy) ──► Segmented MP4s ──► /data/recordings       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Components Detail

1.  **Backend (FastAPI):**
    *   **API:** RESTful endpoints for stream CRUD, status, transcripts, faces, recordings.
    *   **Workers:**
        *   **Audio Worker:** Transcription (Whisper).
        *   **Face Worker:** Detection & Recognition (InsightFace).
        *   **Recording Worker:** 24/7 Segmentation (FFmpeg).
    *   **Services:**
        *   **Indexer:** Watches `/data/recordings` to update DB.
        *   **Broadcaster:** SSE events for UI.

2.  **go2rtc (Video Engine):**
    *   Handles RTSP ingestion, WebRTC restreaming, MSE/HLS generation.
    *   Internal Ports: API(`8954`), RTSP(`8955`), WebRTC(`8956`).

3.  **WhisperLive (AI):**
    *   Dedicated container for Faster-Whisper.

---

## 5. Current System State

**Date:** 2026-01-01
**Version:** 0.3.0

### Key Features
1.  **NVR Recording:** Continuous 24/7 recording (MP4 segments) with auto-cleanup.
2.  **Face Recognition (Upgrade):** Robust identity management with multi-embedding support, running average matching, and event snapshots.
3.  **Pretraining:** Auto-register known faces by dropping images into `/data/faces/known/{name}/`.
4.  **Playback UI:** Calendar-based timeline and video player.
5.  **Anti-Hallucination Audio:** 6-layer filtering (Bandpass, Energy, VAD, Confidence, Blacklist).

### Dependencies Added (v0.3.0+)
*   `watchdog` - For recording indexer.
*   `insightface`, `onnxruntime` - For face detection.
*   `alembic` - For database migrations.
*   `silero-vad` - For high-accuracy voice activity detection.

---

## 6. Development Workflow

### Step 1: Diagnose
*   **Logs:** `docker logs -f thewallflower`
*   **API Health:** `curl http://thewallflower:8953/api/health`
*   **Version:** `curl http://thewallflower:8953/api/version`

### Step 2: Implement
*   Modify code in `/config/workspace/TheWallflower`
*   Key files: `worker.py`, `recording_worker.py`, `face_worker.py`, `main.py`

### Step 3: Test (Local Logic)
*   Verify syntax: `python -m py_compile backend/app/main.py`
*   Run unit tests: `pytest backend/tests`

### Step 4: Deploy
```bash
git add .
git commit -m "Fix: ..."
git push
```
*Inform the user to wait for the build.*

---

## 7. Session Management & Continuity

### Proactive Documentation
Update `agents/HANDOFF.md` after every major task completion. This ensures:
- State is captured before account limits or context resets
- New sessions can quickly resume work
- No work is lost if a session ends unexpectedly

**When to update HANDOFF.md:**
- After fixing a bug or implementing a feature
- After completing a code review
- After creating a new plan document
- Before ending any session

### Atomic Task Execution
Break work into smaller chunks that complete fully before moving on:
- Each task should result in a working state
- Commit frequently (don't batch large changes)
- If a task is too large, create a plan document first
- Mark todos as complete immediately when done

**Example of atomic work:**
```
1. Fix bug A → commit → push
2. Fix bug B → commit → push
3. Update docs → commit → push
```

**NOT this:**
```
1. Fix bugs A, B, C, D all at once → one giant commit
```

This approach ensures that if a session ends mid-work, maximum progress is preserved and deployable.

---

## 8. Troubleshooting Cheat Sheet

| Issue | Check |
|-------|-------|
| "Connection Refused" to go2rtc | `docker exec thewallflower ps aux` - is go2rtc running? |
| "Stream Failed" (WebRTC) | Check STUN config, Nginx proxy for `/api/streams/.../webrtc` |
| "Disk I/O Error" (SQLite) | Check volume mounts in `docker-compose.yml` (Use relative `./data:/data`) |
| High CPU | Increase `FACE_DETECTION_INTERVAL` (default 1.0s) |
| Missing Recordings | Check `RecordingWorker` logs (`ffmpeg` stderr) |

---

## 9. File Reference

| File | Purpose |
|------|---------|
| `backend/app/worker.py` | Audio extraction, filtering, Whisper connection |
| `backend/app/workers/recording_worker.py` | NVR recording (FFmpeg subprocess) |
| `backend/app/workers/face_worker.py` | Face detection loop |
| `backend/app/services/recording_indexer.py` | File system watcher |
| `frontend/src/lib/components/StreamCard.svelte` | Main UI with Live/Recording tabs |
| `frontend/src/lib/components/RecordingsPanel.svelte` | Calendar & Playback UI |

---

## Please now read HANDOFF.md and current_errors.md
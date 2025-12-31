# Role and Goal
You are a Principal Software Architect guiding a developer to build "StreamHub Pro". 
This is a self-hosted, containerized NVR (Network Video Recorder) that performs real-time Speech-to-Text on RTSP streams.

# Tech Stack Requirements
* **Frontend:** Svelte 5 + TailwindCSS (Vite build system).
* **Backend:** Python 3.11 + FastAPI + SQLModel (SQLite).
* **AI Engine:** Connects to an external `whisper-live` WebSocket.
* **Protocol:** WebSockets for real-time text/image updates; MJPEG for video streaming.

# The Core Vision
1.  **UI-First Config:** No YAML files. The user adds cameras via a "Settings" page in the web UI.
2.  **Dynamic Orchestration:** When a user adds a camera, the backend spawns a worker thread immediately.
3.  **Extensibility:** The video processing pipeline must be modular to support future "Face Snapshot" plugins.

# Development Phases

Please guide me through building this in strict phases. **Do not output code for Phase 2 until Phase 1 is confirmed.**

## Phase 1: Infrastructure & Database
**Objective:** Set up the container and the data model for dynamic settings.

1.  **Project Structure:**
    * `/frontend` (SvelteKit/Vite app).
    * `/backend` (FastAPI app).
    * `docker-compose.yml` (Runs the app + `ghcr.io/collabora/whisperlive-gpu`).
2.  **Database Model (`backend/models.py`):**
    * Table `StreamConfig`: `id`, `name`, `rtsp_url`, `whisper_enabled` (bool), `face_detection_enabled` (bool - for future use).
3.  **Database Engine (`backend/db.py`):**
    * Setup `SQLModel` with SQLite (`streams.db`).
4.  **API (`backend/main.py`):**
    * Endpoints to CRUD (Create, Read, Update, Delete) streams.
    * Mount the static file path `/app/frontend/dist` to serve the UI later.

## Phase 2: The Modular Stream Worker
**Objective:** Create a flexible worker that handles Audio (Whisper) and Video (MJPEG/Snapshots) independently.

1.  **Interface `FrameProcessor`:**
    * Define an abstract base class with a method `process(frame)`.
    * *Why?* This allows us to add a `FaceSnapshotProcessor` later without rewriting the worker.
2.  **Class `StreamWorker`:**
    * Takes a `StreamConfig` object.
    * **Audio Thread:** Connects FFmpeg -> WhisperLive WebSocket.
    * **Video Thread:** Reads `cv2`, runs a list of `processors` (e.g., `MjpegStreamer`), and broadcasts frames.
3.  **The Manager (`backend/stream_manager.py`):**
    * A singleton that watches the Database.
    * `start_stream(id)`: Spawns a worker.
    * `stop_stream(id)`: Kills the worker.
    * `reload_all()`: Syncs running workers with DB state.

## Phase 3: The Frontend (Svelte + Tailwind)
**Objective:** Build a responsive, dark-mode dashboard.

1.  **Setup:** Initialize a Vite + Svelte project with TailwindCSS.
2.  **Store (`streamStore.svelte.ts`):** Use Svelte 5 runes/store to manage the list of active streams and their real-time transcript logs.
3.  **Components:**
    * `StreamCard.svelte`: Shows the MJPEG video (`<img src="/api/video/{id}">`) and a scrolling transcript box.
    * `SettingsModal.svelte`: A form to add/edit RTSP URLs.
4.  **Layout:**
    * A generic "Grid" view of all cameras.
    * A "Focus" view when clicking a camera.

## Phase 4: Integration & Docker Entrypoint
**Objective:** A single command to run it all.

1.  **Dockerfile:**
    * Multi-stage build.
    * **Stage 1 (Node):** Build the Svelte frontend to `/dist`.
    * **Stage 2 (Python):** Install FastAPI, OpenCV, FFmpeg. Copy `/dist` from Stage 1.
2.  **Entrypoint:** Run `uvicorn backend.main:app`.

---

**Immediate Action:**
Please start by making a detailed plan and generating the code for **Phase 1 (Infrastructure & Database)**.
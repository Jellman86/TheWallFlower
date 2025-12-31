# TheWallflower - Agent Grounding & System Architecture

## Core Mandate
You are working on **TheWallflower**, a self-hosted NVR (Network Video Recorder) with real-time Speech-to-Text capabilities.

## System Architecture

The system uses a **Split-Pipeline Architecture** to handle high-performance video streaming and heavy AI transcription simultaneously without blocking.

```mermaid
graph TD
    User[User Browser]
    Nginx[Nginx Reverse Proxy]
    Backend[FastAPI Backend :8000]
    Go2RTC[go2rtc Streaming Server :1985]
    Whisper[WhisperLive AI :9090]
    Camera[RTSP Camera]

    User -- HTTPS/WebRTC --> Nginx
    Nginx -- Proxy --> Backend
    
    subgraph "TheWallflower Container"
        Backend -- "1. Add Stream" --> Go2RTC
        Backend -- "2. Proxy Signaling" --> Go2RTC
        
        Go2RTC -- "3. RTSP Ingest" --> Camera
        
        Backend -- "4. Audio Extraction (FFmpeg)" --> Go2RTC
        Backend -- "5. Audio Websocket" --> Whisper
    end
    
    Go2RTC -- "6. WebRTC/MJPEG Video" --> User
```

### Key Components

1.  **Frontend (Svelte 5):**
    *   **WebRTCPlayer.svelte:** Handles the "Offer/Answer" exchange. It creates an `RTCPeerConnection`, generates an Offer, and sends it to the backend. It waits for ICE candidates (STUN) before sending to ensure connectivity behind NATs.
    *   **StreamCard.svelte:** Wraps the player. Handles UI state (loading, error, retry). Fallback to MJPEG if WebRTC fails.

2.  **Backend (FastAPI):**
    *   **Role:** Acts as the *Control Plane* and *Signaling Proxy*.
    *   **Signaling Proxy:** The browser never talks to `go2rtc` directly (to avoid CORS/Mixed Content issues). All WebRTC offers/answers are proxied via `/api/streams/{id}/webrtc`.
    *   **Worker (worker.py):** Responsible *only* for Audio. It pulls a local RTSP stream from `go2rtc` (`rtsp://localhost:8955/...`), extracts audio via FFmpeg, and sends it to WhisperLive. **It does not touch video.**

3.  **go2rtc (Video Engine):**
    *   Running inside the same container.
    *   **Ports:** API (`8954`), RTSP (`8955`), WebRTC (`8956`). (Offset from standard Frigate ports to prevent conflicts).
    *   **Role:** Connects to external cameras. Re-streams as WebRTC (low latency) and MJPEG (compatibility).

## The WebRTC Connection Flow (Debugging Context)

When a user views a stream, this sequence happens:

1.  **Frontend:** `WebRTCPlayer` initializes `RTCPeerConnection`.
2.  **Frontend:** Generates SDP Offer.
3.  **Frontend:** Waits for ICE Candidates (STUN). *Critical: If this times out, connection fails.*
4.  **Frontend:** POSTs Offer to `https://thewallflower.../api/streams/1/webrtc`.
5.  **Backend:** Proxies request to `http://localhost:8954/api/webrtc...`.
6.  **go2rtc:** Processes Offer, generates Answer.
7.  **Backend:** Returns Answer to Frontend.
8.  **Frontend:** Sets Remote Description. Video starts flowing via UDP/TCP.

## Debugging Guide

### Common Failure Modes

*   **"Stream Failed" / ICE Timeout:**
    *   **Cause:** Browser couldn't find a path to the server.
    *   **Fix:** Check STUN settings in `WebRTCPlayer.svelte` and `docker-entrypoint.sh`. Ensure UDP ports `8956` (or range) are exposed if running outside host network mode (though Nginx usually handles TCP tunneling).
*   **"Server Error 404/500" during negotiation:**
    *   **Cause:** Backend can't talk to `go2rtc`.
    *   **Check:** `docker logs thewallflower`. Look for "Connection refused" to `localhost:8954`.
*   **Video works, Audio Transcription dead:**
    *   **Cause:** `worker.py` failed to connect to Whisper or `go2rtc` RTSP.
    *   **Check:** `/api/streams/{id}/status`. Look for `audio_connected: false`.

### Useful Commands (Inside Container) remember you cannot interact with docker directly, it must be done via testing api.

*   **Check Processes:** `ps aux | grep -E "go2rtc|python"`
*   **Check Logs:** `docker logs -f thewallflower` (Enabled `debug` level for go2rtc).
*   **Manual Stream Check:**
    *   Status: `curl http://localhost:8954/api/streams`
    *   Health: `curl http://localhost:8953/api/health`

### Test Resources

*   **Confirmed Working RTSP:** `rtsp://Jellman86:o7zlFClGhWL0l7@192.168.214.157/stream1`
*   **Internal Service DNS:**
    *   Main App: `thewallflower`
    *   Whisper: `whisper-live`

## Operational Constraints

*   **Docker Access:** You do NOT have access to the Docker daemon. Do not run `docker` commands (ps, logs, restart).
*   **Connectivity:** `localhost` refers to your local agent environment, NOT the application container. You cannot connect to the app via `localhost`.
*   **Testing:** Use Docker DNS names to interact with the API (e.g., `http://thewallflower:8953`).
*   **Modifying Files:** Always use `read_file` before `replace`. Context is key.
*   **Restarting:** If you modify `main.py` or `worker.py`, the changes usually auto-reload in dev mode, but a container restart is safer for deep architectural changes.
*   **Network:** You are behind Nginx. Do not assume direct external access. Always proxy through the Backend API.

## Current System State (Dec 31, 2025)

*   **WebRTC:** Enabled and primary.
*   **go2rtc Config:**
    *   STUN: `stun:stun.l.google.com:19302` enabled.
    *   Log Level: `debug`.
*   **Frontend:** `WebRTCPlayer` has 3s ICE timeout.
*   **Backend:** Enhanced logging on all proxy endpoints.
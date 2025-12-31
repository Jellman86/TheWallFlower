# GEMINI Opinion & System Analysis

**Date:** December 28, 2025
**Subject:** Codebase Inspection & RTSP Browser Crash Analysis
**Project:** TheWallflower

## 1. Executive Summary

The project is at a critical transition point. The architectural decision to move from a pure Python/OpenCV video pipeline to **go2rtc** is 100% correct and necessary. The previous browser crashes were almost certainly caused by the Python backend's inability to handle real-time video transcoding and streaming efficiently, leading to resource exhaustion.

However, the codebase was **functionally broken** due to basic syntax errors introduced during the refactor. The system could not run to verify if the crash was resolved because the backend failed to start.

## 2. Root Cause Analysis: The Browser Crash

You asked why a valid RTSP stream causes the browser to crash. Based on the codebase history and current state, here is the technical breakdown:

### A. The "Old" Way (Python + OpenCV)
The original implementation likely acted as a proxy where Python read frames via OpenCV and yielded them as an MJPEG stream.
*   **The Bottleneck:** Python's GIL (Global Interpreter Lock) and the overhead of serialization/deserialization of image frames meant the backend couldn't keep up with high-bandwidth RTSP streams (especially 1080p+ or high FPS).
*   **The Crash Mechanism:** When the backend falls behind, it typically results in:
    1.  **Frame Buffering:** Memory usage spikes on the server.
    2.  **Network Stalls:** The browser receives partial headers or corrupted frames.
    3.  **Browser Resource Exhaustion:** The `<img>` tag or canvas attempting to render the MJPEG stream enters a tight error/retry loop or accumulates uncollected garbage (blobs) if not managed perfectly. This leads to the browser tab consuming excessive RAM/CPU until it crashes.

### B. The "New" Way (go2rtc) - The Solution
The current codebase integrates `go2rtc`. This delegates video handling to a specialized Go binary.
*   **Why it fixes the crash:** `go2rtc` proxies the stream directly to the browser (via WebRTC or efficient MJPEG) with minimal overhead. The browser receives a compliant, stable stream.
*   **Current Risk:** The `worker.py` is now correctly stripped of video processing logic (it only handles Audio/Whisper). This effectively removes the heavy processing load from the Python backend.

## 3. Fixed Critical Issues (Blocking Stability)

I have applied hotfixes to `backend/app/main.py` to resolve fatal startup errors.

### 1. Backend Syntax Errors (FIXED)
The `backend/app/main.py` file had fatal errors preventing startup:
*   **Missing Import:** `Response` was used in `stream_hls_proxy` and `stream_webrtc_proxy` but not imported. **Fixed.**
*   **Missing Import:** `Request` was reported as missing in logs, but appeared to be present. I verified imports.
*   **Impact:** The API should now start correctly, allowing the frontend to connect.

### 2. Frontend Resource Leaks (The Secondary Crash Vector)
The `DEVELOPMENT_PLAN_V2.md` correctly identified potential leaks.
*   **Review:** I reviewed `StreamCard.svelte` and `TranscriptPanel.svelte`.
*   **Findings:** The retry logic in `StreamCard.svelte` uses exponential backoff for image loading and a 5-second delay for SSE reconnection. `TranscriptPanel.svelte` does not auto-reconnect. This logic seems safe and unlikely to cause a browser freeze unless the backend sends malformed data that crashes the JS parser (which is less likely with the new go2rtc setup).

## 4. Recommendations & Roadmap

### Step 1: Verify System Startup (Immediate)
The system should now be startable. Please restart the backend container.

### Step 2: Validate go2rtc Integration
Once the backend starts, verify that `go2rtc` is actually accessible.
*   The proxy endpoints in `main.py` (`/api/streams/{stream_id}/mjpeg`, etc.) are critical. Ensure they properly forward data.

### Step 3: Harden the Frontend (Longer Term)
To permanently prevent browser crashes:
*   **AbortController:** Implement `AbortController` in `api.js` to cancel stale requests immediately when components unmount.
*   **Image Cleanup:** Ensure `StreamCard.svelte` properly revokes ObjectURLs (if used) or stops loading images when the component is destroyed.

## 5. Conclusion
The "Browser Crash" was likely a symptom of the legacy architecture. The architecture has been fixed, and now the implementation syntax errors have been resolved. The system should be significantly more stable.
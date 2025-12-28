# GEMINI Opinion & System Analysis

**Date:** December 28, 2025
**Subject:** Codebase Inspection & RTSP Browser Crash Analysis
**Project:** TheWallflower

## 1. Executive Summary

The project is at a critical transition point. The architectural decision to move from a pure Python/OpenCV video pipeline to **go2rtc** is 100% correct and necessary. The previous browser crashes were almost certainly caused by the Python backend's inability to handle real-time video transcoding and streaming efficiently, leading to resource exhaustion.

However, the current codebase is **functionally broken** due to basic syntax errors introduced during the refactor. The system cannot currently run to verify if the crash is resolved because the backend fails to start.

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

## 3. Current Critical Issues (Blocking Stability)

Despite the architectural improvements, the application is currently in a **failed state**.

### 1. Backend Syntax Errors (Immediate Blocker)
The `backend/app/main.py` file has fatal errors preventing startup:
*   **Missing Import:** `Request` is used in `stream_webrtc_proxy` (line 597) but not imported from `fastapi`.
*   **Missing Import:** `json` is likely missing (referenced in `DEVELOPMENT_PLAN_V2.md`).
*   **Impact:** The API crashes on boot. The frontend cannot connect, so it may enter a rapid retry loop, which ironically acts as a DOS attack on your own browser, potentially simulating a "crash".

### 2. Frontend Resource Leaks (The Secondary Crash Vector)
The `DEVELOPMENT_PLAN_V2.md` correctly identifies leaks in `TranscriptPanel.svelte` and `StreamCard.svelte`.
*   **SSE Leaks:** `EventSource` connections are not always cleanly closed or deduped.
*   **Retry Logic:** If the backend is down (as it is now), the frontend components might be aggressively retrying requests without sufficient backoff or cleanup, leaking memory in the JavaScript heap.

## 4. Recommendations & Roadmap

### Step 1: Fix the Plumbing (P0)
You must apply the hotfixes before any further debugging.
*   **Action:** Add `from fastapi import Request` to `backend/app/main.py`.
*   **Action:** Add `import json` to `backend/app/main.py`.

### Step 2: Validate go2rtc Integration (P0)
Once the backend starts, verify that `go2rtc` is actually accessible.
*   The proxy endpoints in `main.py` (`/api/streams/{stream_id}/mjpeg`, etc.) are critical. Ensure they properly forward data and don't deadlock if `go2rtc` is offline.

### Step 3: Harden the Frontend (P1)
To permanently prevent browser crashes:
*   **AbortController:** Implement `AbortController` in `api.js` to cancel stale requests immediately when components unmount.
*   **Image Cleanup:** Ensure `StreamCard.svelte` properly revokes ObjectURLs (if used) or stops loading images when the component is destroyed.

## 5. Conclusion
The "Browser Crash" was likely a symptom of the legacy architecture. The architecture has been fixed, but the code implementation is currently incomplete (broken imports). Fix the syntax errors, and the system should be significantly more stable.

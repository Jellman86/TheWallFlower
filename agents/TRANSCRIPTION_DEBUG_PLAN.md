# Transcription Debugging & Resolution Plan (Updated Dec 31, 2025)

## Goal
Restore real-time speech-to-text functionality and ensure system stability.

## Current Status
- Stream Auto-start: **Success**
- WebSocket Handshake: **Success**
- Audio Data Flow: **Success**
- AI Processing: **Success** (VAD filtering working, transcripts being received)

---

## Phase 0: Auto-start & UI Sync (COMPLETED)
Streams now correctly sync their status to the UI on load.
1.  **Global SSE Status**: Updated `global_events` to broadcast current stream statuses upon connection.
2.  **go2rtc Integration**: Python workers correctly pull audio from go2rtc RTSP restreams.

## Phase 1: Audio Pipeline Stabilization (COMPLETED)
Restored audio flow by identifying and fixing numerical errors.
1.  **Filter Removal**: Removed aggressive bandpass filters that caused `RuntimeWarning: overflow encountered in square` in WhisperLive.
2.  **Handshake Fix**: Standardized the handshake JSON to be compatible with `faster_whisper` backend.
3.  **Local Verification**: Successfully ran manual WebSocket tests confirming `SERVER_READY` and transcript reception.

## Phase 2: Hallucination Mitigation (COMPLETED)
Resolved "noise-to-text" issues.
1.  **VAD Re-enabled**: Re-enabled `use_vad: True` to ensure silence or low-level static isn't interpreted as speech.
2.  **Volume Normalization**: Tuned FFmpeg volume boost to `1.5x` (down from `3.0x`) to prevent clipping.
3.  **Segment Parsing**: Updated `worker.py` to handle both `text` and `segments` list formats from WhisperLive.

## Phase 3: Connection Robustness (COMPLETED)
Ensured SSE and WebSocket connections remain stable.
1.  **SSE Heartbeat**: Reduced keepalive from 15s to 5s.
2.  **Handshake Logs**: Added `INFO` level logging for all incoming AI messages.

## Phase 4: Final Verification (IN PROGRESS)
1.  **User Confirmation**: Waiting for user to confirm transcription appears in UI when speaking.
2.  **Long-term Stability**: Monitor logs for memory leaks or FFmpeg zombie processes.
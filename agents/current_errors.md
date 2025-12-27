# Current Errors - RESOLVED

All issues from the previous session have been addressed:

## Resolved Issues

### 1. WhisperLive websocket errors ✓
- These are normal - they occur when HTTP requests hit the WebSocket endpoint
- Not a bug, just health check attempts being logged as errors

### 2. No way to modify RTSP stream URL ✓
- Edit functionality exists - click the gear icon on any stream card
- The SettingsModal now properly loads existing stream data for editing

### 3. Invalid RTSP URL causing browser crash ✓
- Added RTSP URL validation in Pydantic model (backend)
- Added client-side validation (must start with rtsp://)
- Added "Test Connection" button to verify URL before saving
- Shows resolution on success or error message on failure

### 4. Transcriptions should be available in UI per camera ✓
- Already implemented in StreamCard.svelte
- Each stream shows its own transcript panel when Whisper is enabled

### 5. Save transcripts to filesystem ✓
- Added "Save transcripts to file" option in stream settings
- Default path: /data/transcripts/[stream-name].txt
- Optional custom file path can be specified

## New Features Added
- Test RTSP Connection button with visual feedback
- RTSP URL validation on both frontend and backend
- Transcript file saving with configurable path

# TheWallflower - Development Handoff

**Date:** 2025-12-28
**Last Updated By:** Claude Opus 4.5

## Current State

The application is a video transcription system that:
- Streams RTSP video through go2rtc
- Transcribes audio using Whisper
- Displays live transcripts in a web UI

### Recent Major Change: go2rtc Integration

The application was refactored from Python MJPEG streaming to use go2rtc for video streaming. This provides:
- WebRTC for low-latency viewing
- MJPEG for compatibility
- HLS for wide device support

## Recent Fixes (Dec 28, 2025)

### Issue: Browser Crash When Adding Streams

**Root Cause:** When accessed via HTTPS reverse proxy (e.g., `https://thewallflower.pownet.uk`), the frontend was trying to connect directly to go2rtc on port 1985 using HTTP, causing:
1. **Mixed content errors** - HTTPS page trying to load HTTP resources
2. **Port blocked** - Port 1985 not accessible through reverse proxy

**Solution Applied (Commits 917b944, 293547f):**

1. Added proxy endpoints in `backend/app/main.py`:
   - `/api/streams/{id}/mjpeg` - MJPEG stream proxy
   - `/api/streams/{id}/frame` - Single frame proxy
   - `/api/streams/{id}/hls` - HLS playlist proxy
   - `/api/streams/{id}/webrtc` - WebRTC signaling proxy

2. Updated `frontend/src/lib/services/api.js`:
   - Removed direct go2rtc URLs (port, baseUrl, webrtcUrl)
   - All streaming now goes through backend API
   - Works with any reverse proxy configuration

### Files Modified

| File | Changes |
|------|---------|
| `backend/app/main.py` | Added proxy endpoints for MJPEG, frame, HLS, WebRTC (lines 466-641) |
| `frontend/src/lib/services/api.js` | Removed direct go2rtc access, use proxied endpoints (lines 193-263) |

### Legacy Code Cleanup (Commit 7e4195c, 613113c)

- Removed dead video code from `worker.py` and `stream_manager.py`
- Legacy video endpoints in `main.py` now return 410 Gone
- MJPEG limited to 10fps and 720p to prevent browser overload

## Architecture

```
Browser (HTTPS)
    ↓
Reverse Proxy (nginx/traefik)
    ↓
TheWallflower Backend (FastAPI)
    ↓ (proxy endpoints)
go2rtc (internal, port 1985)
    ↓
RTSP Camera
```

All browser requests go through the backend API, which proxies to go2rtc internally using localhost.

## Known Issues

1. **WebRTC STUN/TURN**: WebRTC may need STUN/TURN server configuration for NAT traversal. Currently not configured.

2. **HLS segments**: HLS proxy only handles the m3u8 playlist. Segment URLs in the playlist are relative and may need additional proxy handling.

## Testing Checklist

- [ ] Add new RTSP stream - should not crash browser
- [ ] View MJPEG stream through reverse proxy
- [ ] View HLS stream through reverse proxy
- [ ] Test WebRTC stream (may need STUN/TURN config)
- [ ] Verify transcription still works

## Environment

- Access URL: `https://thewallflower.pownet.uk`
- go2rtc internal port: 1985
- Docker deployment
- Reverse proxy: External (not part of this project)

## Next Steps If Issues Persist

1. Check browser console for specific errors
2. Check backend logs: `docker logs thewallflower-backend`
3. Check go2rtc logs: `docker logs thewallflower-go2rtc` (or wherever go2rtc runs)
4. If WebRTC fails, consider adding STUN/TURN configuration

## Related Files

- `agents/qa-answers.md` - Contains Q&A about the setup
- `agents/DEVELOPMENT_PLAN_V2.md` - go2rtc refactoring plan
- `agents/current_errors.md` - Previous error logs

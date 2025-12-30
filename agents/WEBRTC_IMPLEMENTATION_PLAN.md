# WebRTC Implementation Plan

## Objective
Replace the current MJPEG image polling with a true WebRTC video player to achieve sub-second latency, smoother playback, and lower CPU usage on the client side.

## Strategy
We will implement a standard "Offer/Answer" WebRTC exchange where the browser (Frontend) acts as the "Offerer" and the Go2RTC server (via the Backend proxy) acts as the "Answerer".

## Tasks

### 1. Create `WebRTCPlayer.svelte` Component
**Location:** `frontend/src/lib/components/WebRTCPlayer.svelte`

This component will encapsulate all WebRTC logic:
- **Initialization:** Create an `RTCPeerConnection`.
- **Negotiation:**
    1. Create a WebRTC Offer (`pc.createOffer`).
    2. Set Local Description.
    3. Send the Offer SDP to the backend endpoint `/api/streams/{id}/webrtc`.
    4. Receive the Answer SDP from the backend.
    5. Set Remote Description.
- **Media Handling:**
    - Listen for the `track` event.
    - Attach the incoming `MediaStream` to a standard HTML5 `<video>` element.
    - Handle autoplay and muting (browsers require mute for autoplay usually, but we want audio if available).
- **State Management:**
    - Handle connection states (`connecting`, `connected`, `failed`).
    - Implement auto-reconnection logic if the stream drops.
- **Cleanup:** Properly close the `RTCPeerConnection` when the component is destroyed to prevent memory leaks.

### 2. Update `StreamCard.svelte`
**Location:** `frontend/src/lib/components/StreamCard.svelte`

- Import the new `WebRTCPlayer` component.
- Add logic to switch between `WebRTCPlayer` and the existing MJPEG `<img>` tag (fallback).
- Set WebRTC as the default view.
- Pass necessary props (stream ID, auto-play preference) to the player.

### 3. Backend Verification
- Ensure the existing proxy endpoint in `backend/app/main.py` correctly forwards the SDP content type and body to Go2RTC. (Review completed, looks correct).

### 4. Testing & Polish
- Verify playback on Firefox/Chrome.
- Verify resource usage.
- Ensure audio is working (if stream has audio).

## Technical Details

**Signaling Flow:**
1. **Frontend:** `const pc = new RTCPeerConnection(config);`
2. **Frontend:** `pc.addTransceiver('video', {direction: 'recvonly'});`
3. **Frontend:** `offer = await pc.createOffer(); await pc.setLocalDescription(offer);`
4. **Frontend:** `POST /api/streams/1/webrtc` with body `offer.sdp`.
5. **Backend:** Proxies POST to `http://localhost:1985/api/webrtc?src=camera_1`.
6. **Go2RTC:** Returns SDP Answer.
7. **Frontend:** `await pc.setRemoteDescription({type: 'answer', sdp: response_sdp});`
8. **Frontend:** Video starts flowing via UDP/TCP to the `pc`.

## Fallback
If WebRTC fails (e.g., restrictive firewall blocking UDP, though Go2RTC supports TCP/HTTP tunneling), the UI should handle the error state. For this iteration, we will display an error message, but in the future, we could auto-fallback to MJPEG.

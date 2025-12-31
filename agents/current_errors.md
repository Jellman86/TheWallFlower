# Current System Errors & Issues (Dec 31, 2025)

## Resolved Issues
- **Transcription Restored**: The audio pipeline was stabilized by removing aggressive FFmpeg filters that caused numerical overflows in the Whisper backend.
- **OpenVINO Model Loading**: Fixed `401 Client Error` when using OpenVINO backend by making `WHISPER_MODEL` configurable and setting it to a valid Hugging Face Repo ID (e.g., `OpenVINO/whisper-tiny-fp16-ov`) instead of OpenAI model names.
- **VAD Hallucinations Fixed**: Re-enabled VAD (Voice Activity Detection) and normalized audio gain to prevent "noise-hallucinations" (e.g., repetitive `))))))`).
- **SSE Stability**: Reduced keepalive timeout from 15s to 5s to prevent connection drops behind reverse proxies.
- **Handshake Compatibility**: Updated the handshake to use standard parameters and added support for the `segments` list format returned by WhisperLive.

## Ongoing Monitoring
- **Quiet Environments**: In extremely quiet rooms, VAD correctly suppresses all output. Transcription will only appear when speech is detected.
- **Browser State**: Monitoring for the "hard lock" browser crash reported previously. Since the move to go2rtc and simplified worker logic, this has not recurred in logs, but needs user confirmation.
- **Global SSE Keepalive**: The 5s keepalive should prevent the "interrupted while page was loading" error in Firefox.

## Technical Debt / Next Steps
- **Model Loading**: WhisperLive still shows some `websockets.exceptions.InvalidMessage: did not receive a valid HTTP request` on some connection attempts, but it recovers and connects.
- **Audio Tuning**: Fine-tuning the `volume` and `highpass` filters for different camera models might be needed.
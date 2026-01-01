# Current System Errors & Issues (Dec 31, 2025)

## Ongoing Monitoring & Issues
- **VAD Hallucinations (PERSISTENT)**: 
    - **Status:** Despite implementing `initial_prompt="Silence."`, `condition_on_previous_text=False`, and bandpass filters, hallucinations (e.g., "Thank you", "The End") are still being reported.
    - **Current Mitigation:** Blacklist filtering and noise reduction are active, but the core "phantom speech" remains a challenge in quiet environments.
    - **Next Investigation:** Tuning `no_speech_threshold` further (currently 0.4) or evaluating a more robust external VAD.
- **Quiet Environments**: With the new `initial_prompt` and filters, VAD should be robust. Monitoring for any edge cases.
- **Browser State**: Monitoring for the "hard lock" browser crash reported previously. Since the move to go2rtc and simplified worker logic, this has not recurred in logs, but needs user confirmation.

## Resolved Issues
- **Transcription Restored**: The audio pipeline was stabilized by removing aggressive FFmpeg filters that caused numerical overflows in the Whisper backend.
- **OpenVINO Model Loading**: Fixed `401 Client Error` when using OpenVINO backend by making `WHISPER_MODEL` configurable and setting it to a valid Hugging Face Repo ID (e.g., `OpenVINO/whisper-tiny-fp16-ov`) instead of OpenAI model names.
- **SSE Stability**: Reduced keepalive timeout from 15s to 5s to prevent connection drops behind reverse proxies.
- **Handshake Compatibility**: Updated the handshake to use standard parameters and added support for the `segments` list format returned by WhisperLive.
- **Global SSE Keepalive**: The 5s keepalive should prevent the "interrupted while page was loading" error in Firefox.

## Technical Debt / Next Steps
- **Model Loading**: WhisperLive still shows some `websockets.exceptions.InvalidMessage: did not receive a valid HTTP request` on some connection attempts, but it recovers and connects.
- **Audio Tuning**: Fine-tuning the `volume` and `highpass` filters for different camera models might be needed.
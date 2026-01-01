# Current System Errors & Issues (Dec 31, 2025)

## Resolved Issues
- **VAD Hallucinations Fixed**: 
    - **Method:** Added `initial_prompt="Silence."` and set `condition_on_previous_text=False` to prevent context loops.
    - **Tuning:** Lowered `no_speech_threshold` to 0.4 and set `logprob_threshold` to -0.8 to filter low-confidence noise.
    - **Filters:** Implemented Bandpass filter (200Hz-8kHz) and removed volume boost to lower noise floor.
    - **Post-Processing:** Expanded blacklist of ignored phrases (e.g., "Subtitle by", "The End").
- **Transcription Restored**: The audio pipeline was stabilized by removing aggressive FFmpeg filters that caused numerical overflows in the Whisper backend.
- **OpenVINO Model Loading**: Fixed `401 Client Error` when using OpenVINO backend by making `WHISPER_MODEL` configurable and setting it to a valid Hugging Face Repo ID (e.g., `OpenVINO/whisper-tiny-fp16-ov`) instead of OpenAI model names.
- **SSE Stability**: Reduced keepalive timeout from 15s to 5s to prevent connection drops behind reverse proxies.
- **Handshake Compatibility**: Updated the handshake to use standard parameters and added support for the `segments` list format returned by WhisperLive.

## Ongoing Monitoring
- **Quiet Environments**: With the new `initial_prompt` and filters, VAD should be robust. Monitoring for any edge cases.
- **Browser State**: Monitoring for the "hard lock" browser crash reported previously. Since the move to go2rtc and simplified worker logic, this has not recurred in logs, but needs user confirmation.
- **Global SSE Keepalive**: The 5s keepalive should prevent the "interrupted while page was loading" error in Firefox.

## Technical Debt / Next Steps
- **Model Loading**: WhisperLive still shows some `websockets.exceptions.InvalidMessage: did not receive a valid HTTP request` on some connection attempts, but it recovers and connects.
- **Audio Tuning**: Fine-tuning the `volume` and `highpass` filters for different camera models might be needed.
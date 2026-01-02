# Research: Audio Optimization & Hallucination Mitigation
**Date:** 2025-12-31
**Context:** Optimizing RTSP-to-Whisper pipeline for TheWallflower NVR.

## 1. Executive Summary
TheWallflower uses a "Split-Pipeline" architecture where video is handled by `go2rtc` and audio is extracted by a Python worker for `WhisperLive`. This research focuses on optimizing the audio extraction step to minimize hallucinations (phantom speech in silence) and ensure high-fidelity transcription.

**Key Findings:**
1.  **Hallucinations in Silence:** Caused by Whisper trying to "find" patterns in noise. Fixes involve aggressive VAD, low-pass filtering, and specific Whisper prompts.
2.  **BirdNET-Go Approach:** Uses FFmpeg to strip video and downsample audio, often to 48kHz or 16kHz depending on the model.
3.  **WhisperLive Best Practices:** The `initial_prompt`, `condition_on_previous_text`, and `no_speech_threshold` are the most critical tuning parameters.

---

## 2. Benchmark Project: BirdNET-Go
**Project:** [BirdNET-Go](https://github.com/tphakala/birdnet-go)
**Goal:** Continuous bird sound identification from RTSP streams.

### Audio Pipeline Strategy
BirdNET-Go ingests RTSP streams and uses FFmpeg to prepare audio for the TensorFlow Lite model.

**FFmpeg Logic (Inferred & Common Patterns):**
-   **Input:** RTSP (TCP transport for reliability).
-   **Filter Complex:**
    -   `highpass=f=200`: Removes low-frequency wind/electrical hum.
    -   `lowpass=f=15000` (BirdNET specific): Birds call up to ~12-15kHz. For human speech, this should be lower (8kHz).
    -   `aresample`: Asynchronous resampling to handle clock drift between IP camera and server.
-   **Output:** PCM/WAV chunks or raw float stream.

**Relevance to TheWallflower:**
We share the same requirement: reliable 24/7 audio extraction from RTSP. The key takeaway is the use of **bandpass filtering** (Highpass + Lowpass) to isolate the "region of interest" (speech vs. bird calls) and remove noise that triggers false positives.

---

## 3. Whisper Hallucination Mitigation
"Hallucinations" in Whisper (e.g., "Thank you", "Subtitle by", "You") occur when the model processes non-speech audio (silence, white noise, fan hum) and forces a text prediction.

### A. The "Silence" Problem
Whisper is trained on weakly labeled internet audio (including subtitles). When it hears silence or static, it often predicts common subtitle closing phrases.

### B. Configuration Fixes (WhisperLive / Faster-Whisper)

#### 1. `initial_prompt` (IMPLEMENTED)
**What:** Priming the model context.
**Value:** `Silence.` or `Start.`
**Effect:** Tells the model the previous context was silence, discouraging it from inventing a continuation of a non-existent conversation.

#### 2. `condition_on_previous_text` (RECOMMENDED)
**What:** Uses the *previous* segment's text as context for the next.
**Risk:** If the previous segment was a hallucination (e.g., "Thank you"), the model will likely repeat it endlessly.
**Fix:** Set to `False` for surveillance/NVR contexts where speech is sporadic and not a continuous narrative.

#### 3. `no_speech_threshold` (RECOMMENDED)
**What:** Confidence threshold (0.0 - 1.0) for the "no speech" token.
**Default:** 0.6
**Tuning:** Lowering to `0.4` makes the model more aggressive at classifying audio as silence.

#### 4. `logprob_threshold` (RECOMMENDED)
**What:** Threshold for average log probability of the tokens.
**Default:** -1.0
**Tuning:** If the average log probability of the generated text is below this, it is treated as a failure/silence. Raising this (e.g., to -0.8) filters out low-confidence hallucinations.

---

## 4. Recommended Audio Pipeline Configuration

### FFmpeg (Audio Extraction)
Optimized for 16kHz Human Speech.

```bash
ffmpeg -loglevel quiet -rtsp_transport tcp -i rtsp://... \
    -vn \
    -af "highpass=f=200,lowpass=f=8000,aresample=async=1" \
    -c:a pcm_f32le -ar 16000 -ac 1 -f f32le pipe:1
```
*   `highpass=f=200`: Removes rumble/hum.
*   `lowpass=f=8000`: Removes high-pitch hiss/static (human speech > 8kHz is rare/sibilance only).
*   `aresample=async=1`: Prevents drift-related buffer underruns/clicks.

### WhisperLive Handshake (JSON)
Recommended structure for `worker.py`:

```json
{
    "uid": "...",
    "language": "en",
    "task": "transcribe",
    "model": "base.en",
    "use_vad": true,
    "vad_parameters": {
        "onset": 0.5,
        "offset": 0.5
    },
    "initial_prompt": "Silence.",
    "condition_on_previous_text": false,
    "logprob_threshold": -0.8,
    "no_speech_threshold": 0.4
}
```

## 5. Implementation Plan

1.  **Refine Filters:** We have already added `lowpass` and `highpass`.
2.  **Update Handshake:** Modify `worker.py` to send `condition_on_previous_text: False` and tuned thresholds.
3.  **Monitor:** Check if "looping" hallucinations disappear.

---
**References:**
- BirdNET-Go Source (General Architecture)
- Whisper Discussions #679, #197
- WhisperLive Issues (Hallucinations)

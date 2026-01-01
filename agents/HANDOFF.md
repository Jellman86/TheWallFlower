# Development Handoff - TheWallflower
**Date:** 2025-12-31
**Status:** System Refined & Grounding Restructured

## 1. IMMEDIATE ACTION REQUIRED
The system has been significantly refined to mitigate audio hallucinations. These changes are **COMMITTED LOCALLY** but need to be **PUSHED** to trigger the CI/CD pipeline.

**Next Agent Task:**
1.  Verify the local commits (`git log`).
2.  Push to remote (`git push`).
3.  Notify the user that the build is in progress.

---

## 2. RECENT ACHIEVEMENTS

### A. Hallucination Mitigation (Whisper/Audio)
We have implemented a multi-layered defense against "ghost" transcripts in quiet rooms:
-   **Audio Filters:** Added `highpass=200` and `lowpass=8000` to the FFmpeg worker. Removed volume boosting.
-   **Whisper Handshake:** Added `initial_prompt="Silence."`, `condition_on_previous_text=False`, and tuned `no_speech_threshold`/`logprob_threshold`.
-   **Blacklist:** Expanded `HALLUCINATION_PHRASES` to catch common Whisper artifacts.

**CRITICAL NOTE:** Despite these improvements, hallucinations are still being observed. The system is better but not "cured". Next steps should involve further tuning of the `no_speech_threshold` or investigating external VAD (like Silero) if the built-in WhisperLive VAD is insufficient.

### B. Agent Grounding & Documentation
-   **Restructured `agent_grounding.md`:** Now contains explicit mandates forbidding manual container builds and explaining the mandatory CI/CD path.
-   **Research Created:** See `RESEARCH_AUDIO_OPTIMIZATION.md` for the deep dive into `birdnet-go` patterns and WhisperLive tuning.

---

## 3. CORE DOCUMENTS TO READ
New agents MUST read these before performing any actions:

1.  **`agents/agent_grounding.md`**: The "Laws of the Project". Explains why you must not run `docker build`.
2.  **`agents/RESEARCH_AUDIO_OPTIMIZATION.md`**: Technical justification for the current audio pipeline.
3.  **`agents/current_errors.md`**: Track what is resolved and what is still under monitoring.

---

## 4. SYSTEM ARCHITECTURE REMINDER
We use a **Split-Pipeline**:
-   **Video:** Handled by `go2rtc` (internal port 8954).
-   **Audio:** Handled by `backend/app/worker.py` (FFmpeg -> WhisperLive).
-   **Deployment:** GitHub Actions -> User Pulls.

## 5. LOCAL COMMITS PENDING PUSH
- `c6662ca`: Restructure agent grounding.
- `105467b`: Update documentation with advanced Whisper settings.
- `e3aec8e`: Apply advanced Whisper configuration and add audio research report.
- `ae02b36`: Update agent documentation with hallucination fixes and system state.
- `0c0fd06`: Refine audio pipeline and Whisper configuration to reduce hallucinations.

**Handoff Complete.**

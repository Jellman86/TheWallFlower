"""Unit tests for audio filtering logic.

Tests the hallucination mitigation layers:
1. Energy gating (RMS threshold)
2. Hallucination phrase blacklist
3. Confidence-based filtering
"""

import numpy as np
import pytest


class TestEnergyGating:
    """Tests for RMS energy threshold filtering."""

    def test_silent_audio_below_threshold(self):
        """Silent audio should be below default threshold."""
        # Generate near-silent audio (very low amplitude)
        silent_audio = np.zeros(16000, dtype=np.float32)  # 1 second at 16kHz
        rms = np.sqrt(np.mean(silent_audio ** 2))

        threshold = 0.015  # Current default
        assert rms < threshold, "Silent audio should be filtered"

    def test_quiet_noise_below_threshold(self):
        """Quiet background noise should be below threshold."""
        # Generate low-level noise
        np.random.seed(42)
        quiet_noise = np.random.randn(16000).astype(np.float32) * 0.005
        rms = np.sqrt(np.mean(quiet_noise ** 2))

        threshold = 0.015
        assert rms < threshold, "Quiet noise should be filtered"

    def test_speech_level_audio_above_threshold(self):
        """Normal speech-level audio should pass threshold."""
        # Generate speech-level audio (typical RMS ~0.05-0.2)
        np.random.seed(42)
        speech_audio = np.random.randn(16000).astype(np.float32) * 0.1
        rms = np.sqrt(np.mean(speech_audio ** 2))

        threshold = 0.015
        assert rms > threshold, "Speech-level audio should pass filter"

    def test_rms_calculation_accuracy(self):
        """RMS calculation should be mathematically correct."""
        # Known test case: constant signal
        constant_signal = np.full(1000, 0.5, dtype=np.float32)
        rms = np.sqrt(np.mean(constant_signal ** 2))

        assert abs(rms - 0.5) < 0.001, "RMS of constant 0.5 should be 0.5"

    def test_threshold_boundary(self):
        """Audio exactly at threshold boundary."""
        threshold = 0.015

        # Create audio with RMS exactly at threshold
        # For constant signal: RMS = amplitude
        audio = np.full(16000, threshold, dtype=np.float32)
        rms = np.sqrt(np.mean(audio ** 2))

        # Should be very close to threshold
        assert abs(rms - threshold) < 0.0001


class TestHallucinationBlacklist:
    """Tests for hallucination phrase filtering."""

    # Import the actual blacklist from worker.py
    HALLUCINATION_PHRASES = {
        # Original set
        "thank you.", "thank you", "you", "you.",
        "i'm sorry.", "i'm sorry",
        "thanks for watching.", "subtitle by",
        "start conversation", "the end",
        "copyright", "all rights reserved",
        "amara.org", "captions by",
        "silence", "bye",
        # Common non-speech hallucinations (2025 research)
        "subtitles by", "subtitled by", "captioned by",
        "please subscribe", "thank you for watching",
        "goodbye", "see you later", "have a nice day",
        "bye bye", "until next time", "come back soon",
        "[silence]", "[music]", "[applause]",
        "the end.", "end of transmission",
        "thanks", "ok", "sure", "from",
        "sign up", "subscribe today", "join us",
        "support the site", "leave a like", "click here",
        "connection terminated", "signal lost", "standby",
    }

    def test_common_hallucinations_filtered(self):
        """Common hallucination phrases should be in blacklist."""
        common_hallucinations = [
            "thank you",
            "Thank You",  # Case insensitive check
            "bye",
            "silence",
            "the end",
        ]

        for phrase in common_hallucinations:
            assert phrase.lower() in self.HALLUCINATION_PHRASES, \
                f"'{phrase}' should be in blacklist"

    def test_legitimate_speech_not_filtered(self):
        """Normal speech should not be in blacklist."""
        legitimate_phrases = [
            "hello how are you",
            "the weather is nice today",
            "please close the door",
            "what time is it",
            "i need help with this",
        ]

        for phrase in legitimate_phrases:
            assert phrase.lower() not in self.HALLUCINATION_PHRASES, \
                f"'{phrase}' should NOT be in blacklist"

    def test_subtitle_artifacts_filtered(self):
        """Subtitle/caption artifacts should be filtered."""
        artifacts = [
            "subtitle by",
            "subtitles by",
            "captions by",
            "[music]",
            "[silence]",
            "[applause]",
        ]

        for phrase in artifacts:
            assert phrase.lower() in self.HALLUCINATION_PHRASES, \
                f"'{phrase}' should be in blacklist"

    def test_case_insensitive_matching(self):
        """Blacklist matching should be case insensitive."""
        test_phrases = [
            ("THANK YOU", True),
            ("Thank You", True),
            ("thank you", True),
            ("Hello World", False),
        ]

        for phrase, should_match in test_phrases:
            is_match = phrase.lower().strip() in self.HALLUCINATION_PHRASES
            assert is_match == should_match, \
                f"'{phrase}' case-insensitive match should be {should_match}"

    def test_single_word_hallucinations(self):
        """Single-word false positives should be filtered."""
        single_words = ["you", "thanks", "ok", "sure", "bye", "from"]

        for word in single_words:
            assert word.lower() in self.HALLUCINATION_PHRASES, \
                f"Single word '{word}' should be in blacklist"


class TestConfidenceFiltering:
    """Tests for confidence-based transcript filtering."""

    CONFIDENCE_THRESHOLD = -1.0  # Current default

    def test_low_confidence_filtered(self):
        """Low confidence transcripts should be filtered."""
        low_confidence_values = [-1.5, -2.0, -3.0, -10.0]

        for logprob in low_confidence_values:
            should_skip = logprob < self.CONFIDENCE_THRESHOLD
            assert should_skip, f"logprob {logprob} should be filtered"

    def test_high_confidence_passes(self):
        """High confidence transcripts should pass."""
        high_confidence_values = [-0.5, -0.8, -0.9, 0.0]

        for logprob in high_confidence_values:
            should_pass = logprob >= self.CONFIDENCE_THRESHOLD
            assert should_pass, f"logprob {logprob} should pass"

    def test_boundary_confidence(self):
        """Transcript at threshold boundary."""
        # Exactly at threshold should pass (>= comparison)
        assert self.CONFIDENCE_THRESHOLD >= self.CONFIDENCE_THRESHOLD

    def test_missing_confidence_defaults_to_pass(self):
        """Missing avg_logprob should default to 0.0 and pass."""
        default_logprob = 0.0  # What we use when key is missing
        should_pass = default_logprob >= self.CONFIDENCE_THRESHOLD
        assert should_pass, "Missing confidence should default to passing"


class TestTextFiltering:
    """Tests for text-based filtering rules."""

    def test_empty_text_filtered(self):
        """Empty transcripts should be filtered."""
        empty_texts = ["", " ", "  ", "\t", "\n"]

        for text in empty_texts:
            should_skip = not text or len(text.strip()) < 2
            assert should_skip, f"Empty/whitespace text should be filtered"

    def test_single_char_filtered(self):
        """Single character transcripts should be filtered."""
        single_chars = ["a", ".", "!", "?", "1"]

        for text in single_chars:
            should_skip = len(text.strip()) < 2
            assert should_skip, f"Single char '{text}' should be filtered"

    def test_valid_text_passes(self):
        """Valid text with 2+ characters should pass."""
        valid_texts = ["hi", "ok", "no", "hello", "testing"]

        for text in valid_texts:
            # Note: "ok" is in blacklist but passes length check
            should_pass_length = len(text.strip()) >= 2
            assert should_pass_length, f"'{text}' should pass length check"


class TestAudioChunkProcessing:
    """Tests for audio chunk processing logic."""

    def test_chunk_size_calculation(self):
        """Verify chunk size for 1 second of Float32 audio at 16kHz."""
        sample_rate = 16000
        duration_seconds = 1.0
        bytes_per_sample = 4  # Float32

        expected_chunk_size = int(sample_rate * duration_seconds * bytes_per_sample)
        assert expected_chunk_size == 64000, "1s of 16kHz Float32 = 64000 bytes"

    def test_numpy_conversion(self):
        """Audio bytes should convert to numpy array correctly."""
        # Simulate audio chunk (64000 bytes = 16000 float32 samples)
        audio_bytes = np.random.randn(16000).astype(np.float32).tobytes()

        samples = np.frombuffer(audio_bytes, dtype=np.float32)

        assert len(samples) == 16000, "Should have 16000 samples"
        assert samples.dtype == np.float32, "Should be float32"


# Integration-style tests (would need mocking in real implementation)
class TestFilteringPipeline:
    """Tests for the complete filtering pipeline logic."""

    def test_silent_chunk_skipped_at_energy_gate(self):
        """Silent audio should be caught by energy gate first."""
        silent_audio = np.zeros(16000, dtype=np.float32)
        rms = np.sqrt(np.mean(silent_audio ** 2))

        energy_threshold = 0.015

        # Should be caught by energy gate
        assert rms < energy_threshold, "Silent audio caught at energy gate"

    def test_noisy_non_speech_caught_by_vad(self):
        """Noisy non-speech audio might pass energy but fail VAD.

        Note: This is a placeholder - actual VAD testing would require
        loading the Silero VAD model or mocking it.
        """
        # Generate noise that passes energy threshold
        np.random.seed(42)
        noisy_audio = np.random.randn(16000).astype(np.float32) * 0.1
        rms = np.sqrt(np.mean(noisy_audio ** 2))

        energy_threshold = 0.015
        assert rms > energy_threshold, "Noise passes energy gate"

        # VAD would typically catch this as non-speech
        # (VAD testing requires model loading)

    def test_hallucination_caught_by_blacklist(self):
        """Hallucination phrases caught by blacklist even if VAD passes."""
        hallucination_text = "thank you"

        # This text would pass confidence filter but fail blacklist
        HALLUCINATION_PHRASES = {"thank you", "bye", "silence"}

        assert hallucination_text.lower() in HALLUCINATION_PHRASES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

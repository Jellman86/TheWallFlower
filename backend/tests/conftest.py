"""Pytest configuration for TheWallflower backend tests."""

import pytest
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


@pytest.fixture
def sample_audio_silent():
    """Generate silent audio sample (1 second at 16kHz)."""
    import numpy as np
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def sample_audio_speech():
    """Generate speech-level audio sample (1 second at 16kHz)."""
    import numpy as np
    np.random.seed(42)
    return np.random.randn(16000).astype(np.float32) * 0.1


@pytest.fixture
def sample_audio_quiet_noise():
    """Generate quiet noise sample (1 second at 16kHz)."""
    import numpy as np
    np.random.seed(42)
    return np.random.randn(16000).astype(np.float32) * 0.005


@pytest.fixture
def hallucination_blacklist():
    """Return the current hallucination blacklist."""
    return {
        "thank you.", "thank you", "you", "you.",
        "i'm sorry.", "i'm sorry",
        "thanks for watching.", "subtitle by",
        "start conversation", "the end",
        "copyright", "all rights reserved",
        "amara.org", "captions by",
        "silence", "bye",
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

"""Tests for audio processing (ffmpeg wrappers)."""

import subprocess
from pathlib import Path
import pytest

from glottisdale.audio import (
    detect_input_type,
    extract_audio,
    get_duration,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_audio_file():
    result = detect_input_type(FIXTURES / "test_tone.wav")
    assert result == "audio"


def test_detect_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        detect_input_type(Path("/nonexistent/file.wav"))


def test_extract_audio_from_audio(tmp_path):
    """Extracting audio from an audio file just resamples."""
    out = tmp_path / "extracted.wav"
    extract_audio(FIXTURES / "test_tone.wav", out)
    assert out.exists()
    assert out.stat().st_size > 0
    duration = get_duration(out)
    assert abs(duration - 2.0) < 0.1


def test_get_duration():
    duration = get_duration(FIXTURES / "test_tone.wav")
    assert abs(duration - 2.0) < 0.1

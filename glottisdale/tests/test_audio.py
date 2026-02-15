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


from glottisdale.audio import cut_clip, generate_silence, concatenate_clips


def test_cut_clip(tmp_path):
    """Cut a 0.5s clip from a 2s source."""
    out = tmp_path / "clip.ogg"
    cut_clip(
        input_path=FIXTURES / "test_tone.wav",
        output_path=out,
        start=0.5,
        end=1.0,
        padding_ms=0,
        fade_ms=10,
    )
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 0.5) < 0.05


def test_cut_clip_with_padding(tmp_path):
    """Padding extends the clip by padding_ms on each side."""
    out = tmp_path / "clip.ogg"
    cut_clip(
        input_path=FIXTURES / "test_tone.wav",
        output_path=out,
        start=0.5,
        end=1.0,
        padding_ms=25,
        fade_ms=10,
    )
    assert out.exists()
    duration = get_duration(out)
    # 0.5s + 2*0.025s padding = 0.55s
    assert abs(duration - 0.55) < 0.05


def test_cut_clip_padding_clamped(tmp_path):
    """Padding at file boundaries is clamped."""
    out = tmp_path / "clip.ogg"
    cut_clip(
        input_path=FIXTURES / "test_tone.wav",
        output_path=out,
        start=0.0,
        end=0.1,
        padding_ms=100,  # Would go negative without clamping
        fade_ms=10,
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_silence(tmp_path):
    """Generate a silent OGG of specified duration."""
    out = tmp_path / "silence.ogg"
    generate_silence(out, duration_ms=100, sample_rate=16000)
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 0.1) < 0.05


def test_concatenate_clips_no_gaps(tmp_path):
    """Concatenate two clips without gaps."""
    # Cut two clips from test tone
    clip1 = tmp_path / "c1.ogg"
    clip2 = tmp_path / "c2.ogg"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 0.5, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.5, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "concat.ogg"
    concatenate_clips([clip1, clip2], out, crossfade_ms=0)
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 1.0) < 0.1


def test_concatenate_with_gaps(tmp_path):
    """Concatenate with silence gaps."""
    clip1 = tmp_path / "c1.ogg"
    clip2 = tmp_path / "c2.ogg"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 0.3, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.5, 0.8, padding_ms=0, fade_ms=0)

    out = tmp_path / "concat.ogg"
    concatenate_clips([clip1, clip2], out, crossfade_ms=0, gap_durations_ms=[200])
    assert out.exists()
    duration = get_duration(out)
    # 0.3 + 0.2 gap + 0.3 = 0.8s
    assert abs(duration - 0.8) < 0.1

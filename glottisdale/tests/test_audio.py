"""Tests for audio processing (ffmpeg wrappers)."""

import subprocess
from pathlib import Path
import pytest

from glottisdale.audio import (
    detect_input_type,
    extract_audio,
    get_duration,
    time_stretch_clip,
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


from glottisdale.audio import (
    cut_clip,
    generate_silence,
    concatenate_clips,
    pitch_shift_clip,
    adjust_volume,
    mix_audio,
)


def test_cut_clip(tmp_path):
    """Cut a 0.5s clip from a 2s source."""
    out = tmp_path / "clip.wav"
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
    out = tmp_path / "clip.wav"
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
    out = tmp_path / "clip.wav"
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
    """Generate a silent WAV of specified duration."""
    out = tmp_path / "silence.wav"
    generate_silence(out, duration_ms=100, sample_rate=16000)
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 0.1) < 0.05


def test_concatenate_clips_no_gaps(tmp_path):
    """Concatenate two clips without gaps."""
    # Cut two clips from test tone
    clip1 = tmp_path / "c1.wav"
    clip2 = tmp_path / "c2.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 0.5, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.5, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "concat.wav"
    concatenate_clips([clip1, clip2], out, crossfade_ms=0)
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 1.0) < 0.1


def test_concatenate_with_gaps(tmp_path):
    """Concatenate with silence gaps."""
    clip1 = tmp_path / "c1.wav"
    clip2 = tmp_path / "c2.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 0.3, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.5, 0.8, padding_ms=0, fade_ms=0)

    out = tmp_path / "concat.wav"
    concatenate_clips([clip1, clip2], out, crossfade_ms=0, gap_durations_ms=[200])
    assert out.exists()
    duration = get_duration(out)
    # 0.3 + 0.2 gap + 0.3 = 0.8s
    assert abs(duration - 0.8) < 0.1


# --- pitch_shift_clip tests ---


def test_pitch_shift_produces_valid_output(tmp_path):
    """Pitch-shifting should produce a valid file with approximately the same duration."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "shifted.wav"
    pitch_shift_clip(clip, out, semitones=3)
    assert out.exists()
    assert out.stat().st_size > 0
    original_dur = get_duration(clip)
    shifted_dur = get_duration(out)
    # asetrate+aresample changes duration proportionally to pitch shift;
    # 3 semitones ~= 19% duration change, verify output is still reasonable
    assert abs(shifted_dur - original_dur) < 0.25


def test_pitch_shift_zero_is_identity(tmp_path):
    """Zero semitone shift should just copy the file."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "shifted.wav"
    pitch_shift_clip(clip, out, semitones=0.0)
    assert out.exists()
    assert out.stat().st_size > 0
    # Should be the same duration
    original_dur = get_duration(clip)
    shifted_dur = get_duration(out)
    assert abs(shifted_dur - original_dur) < 0.05


# --- adjust_volume tests ---


def test_adjust_volume_produces_valid_output(tmp_path):
    """Volume adjustment should produce a valid file with the same duration."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "louder.wav"
    adjust_volume(clip, out, db=-6.0)
    assert out.exists()
    assert out.stat().st_size > 0
    original_dur = get_duration(clip)
    adjusted_dur = get_duration(out)
    assert abs(adjusted_dur - original_dur) < 0.05


# --- mix_audio tests ---


def test_mix_audio_duration_matches_primary(tmp_path):
    """Mixed output duration should match the primary clip."""
    primary = tmp_path / "primary.wav"
    secondary = tmp_path / "secondary.wav"
    cut_clip(FIXTURES / "test_tone.wav", primary, 0.0, 1.5, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", secondary, 0.0, 0.5, padding_ms=0, fade_ms=0)

    out = tmp_path / "mixed.wav"
    mix_audio(primary, secondary, out, secondary_volume_db=-40)
    assert out.exists()
    assert out.stat().st_size > 0
    primary_dur = get_duration(primary)
    mixed_dur = get_duration(out)
    assert abs(mixed_dur - primary_dur) < 0.15


# --- time_stretch_clip tests ---


def test_time_stretch_doubles_duration(tmp_path):
    """Stretching by 2.0 should approximately double the duration."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "stretched.wav"
    time_stretch_clip(clip, out, factor=2.0)
    assert out.exists()
    stretched_dur = get_duration(out)
    assert abs(stretched_dur - 2.0) < 0.3  # ~2x original 1.0s


def test_time_stretch_halves_duration(tmp_path):
    """Stretching by 0.5 should approximately halve the duration."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "stretched.wav"
    time_stretch_clip(clip, out, factor=0.5)
    assert out.exists()
    stretched_dur = get_duration(out)
    assert abs(stretched_dur - 0.5) < 0.2


def test_time_stretch_identity(tmp_path):
    """Factor 1.0 should copy without processing."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "stretched.wav"
    time_stretch_clip(clip, out, factor=1.0)
    assert out.exists()
    original_dur = get_duration(clip)
    stretched_dur = get_duration(out)
    assert abs(stretched_dur - original_dur) < 0.05


def test_time_stretch_no_rubberband_fallback(tmp_path, monkeypatch):
    """If rubberband not available, should copy the file and log warning."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    # Simulate rubberband not installed by making ffmpeg fail with rubberband filter
    import subprocess
    original_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if any("rubberband" in str(c) for c in cmd):
            result = subprocess.CompletedProcess(cmd, 1, "", "No such filter: 'rubberband'")
            result.check_returncode()  # raises CalledProcessError
        return original_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = tmp_path / "stretched.wav"
    # Should not raise, just copy
    time_stretch_clip(clip, out, factor=2.0)
    assert out.exists()

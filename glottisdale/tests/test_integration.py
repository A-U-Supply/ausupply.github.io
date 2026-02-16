"""Integration test: full pipeline with real ffmpeg, mocked Whisper."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from glottisdale import process


@pytest.mark.integration
@patch("glottisdale.align.transcribe")
def test_full_pipeline_local_mode(mock_transcribe, tmp_path):
    """End-to-end: generate test audio → process → verify output."""
    import subprocess

    # Generate a 3-second test WAV with speech-like characteristics
    input_wav = tmp_path / "input.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-ar", "16000", "-ac", "1",
        str(input_wav),
    ], capture_output=True, check=True)

    # Mock Whisper to return fake word timestamps
    mock_transcribe.return_value = {
        "text": "hello beautiful world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.8},
            {"word": "beautiful", "start": 0.9, "end": 1.8},
            {"word": "world", "start": 1.9, "end": 2.5},
        ],
        "language": "en",
    }

    output_dir = tmp_path / "output"
    result = process(
        input_paths=[input_wav],
        output_dir=output_dir,
        target_duration=5.0,
        crossfade_ms=0,
        padding_ms=10,
        phrase_pause="0",
        sentence_pause="0",
        word_crossfade_ms=0,
        seed=42,
    )

    # Verify outputs exist
    assert output_dir.exists()
    assert (output_dir / "clips").is_dir()
    assert result.concatenated.exists()
    assert (output_dir / "clips.zip").exists()
    assert (output_dir / "manifest.json").exists()

    # Verify manifest
    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["sources"] == ["input"]
    assert len(manifest["clips"]) > 0

    # Verify clips are real WAV files
    for clip in result.clips:
        assert clip.output_path.exists()
        assert clip.output_path.stat().st_size > 0

    # 6 syllables grouped into variable-length words — at least 2 words
    assert len(result.clips) >= 2


@pytest.mark.integration
@patch("glottisdale.align.transcribe")
def test_audio_polish_integration(mock_transcribe, tmp_path):
    """End-to-end test with audio polish features enabled."""
    import subprocess

    input_wav = tmp_path / "input.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=200:duration=4",
        "-ar", "16000", "-ac", "1",
        str(input_wav),
    ], capture_output=True, check=True)

    mock_transcribe.return_value = {
        "text": "hello beautiful world today",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "beautiful", "start": 0.6, "end": 1.3},
            {"word": "world", "start": 1.8, "end": 2.3},
            {"word": "today", "start": 2.8, "end": 3.5},
        ],
        "language": "en",
    }

    output_dir = tmp_path / "output"
    result = process(
        input_paths=[input_wav],
        output_dir=output_dir,
        target_duration=10.0,
        seed=42,
        noise_level_db=-40,
        room_tone=True,
        pitch_normalize=True,
        pitch_range=5,
        breaths=True,
        breath_probability=1.0,
        volume_normalize=True,
        prosodic_dynamics=True,
    )

    assert result.concatenated.exists()
    assert result.concatenated.stat().st_size > 0
    from glottisdale.audio import get_duration
    dur = get_duration(result.concatenated)
    assert dur > 0


@pytest.mark.integration
@patch("glottisdale.align.transcribe")
def test_audio_polish_all_disabled(mock_transcribe, tmp_path):
    """Audio polish features can all be disabled."""
    import subprocess

    input_wav = tmp_path / "input.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-ar", "16000", "-ac", "1",
        str(input_wav),
    ], capture_output=True, check=True)

    mock_transcribe.return_value = {
        "text": "hello world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.8},
            {"word": "world", "start": 1.0, "end": 2.0},
        ],
        "language": "en",
    }

    output_dir = tmp_path / "output"
    result = process(
        input_paths=[input_wav],
        output_dir=output_dir,
        target_duration=5.0,
        crossfade_ms=0,
        padding_ms=10,
        phrase_pause="0",
        sentence_pause="0",
        word_crossfade_ms=0,
        seed=42,
        noise_level_db=0,
        room_tone=False,
        pitch_normalize=False,
        breaths=False,
        volume_normalize=False,
        prosodic_dynamics=False,
    )

    assert result.concatenated.exists()
    assert result.concatenated.stat().st_size > 0

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
        gap="0",
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

    # Verify clips are real OGG files
    for clip in result.clips:
        assert clip.output_path.exists()
        assert clip.output_path.stat().st_size > 0

    # "hello" = 2 syllables, "beautiful" = 3 syllables, "world" = 1 syllable = 6 total
    assert len(result.clips) >= 3  # at least some syllables selected

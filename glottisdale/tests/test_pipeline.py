"""Tests for the pipeline orchestrator."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from glottisdale import process
from glottisdale.types import Syllable, Phoneme


def _make_syllables():
    """Fake syllables spanning 0-2 seconds across two words."""
    return [
        Syllable([Phoneme("HH", 0.0, 0.1), Phoneme("AH0", 0.1, 0.25)],
                 0.0, 0.25, "hello", 0),
        Syllable([Phoneme("L", 0.25, 0.35), Phoneme("OW1", 0.35, 0.5)],
                 0.25, 0.5, "hello", 0),
        Syllable([Phoneme("W", 0.6, 0.7), Phoneme("ER1", 0.7, 0.85),
                  Phoneme("L", 0.85, 0.92), Phoneme("D", 0.92, 1.0)],
                 0.6, 1.0, "world", 1),
    ]


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_local_file(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    # Setup mocks
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    # Make cut_clip create empty files
    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    # Make concat create empty file
    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
    )

    assert result.transcript == "[audio] hello world"
    assert len(result.clips) >= 1  # 3 syllables grouped into variable-length words
    assert result.concatenated.exists()
    assert (tmp_path / "out" / "manifest.json").exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_respects_target_duration(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    # Create many syllables (10 x 0.2s = 2s total)
    syllables = [
        Syllable([Phoneme("AH0", i * 0.2, (i + 1) * 0.2)],
                 i * 0.2, (i + 1) * 0.2, f"word{i}", i)
        for i in range(10)
    ]

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "test",
        "words": [],
        "syllables": syllables,
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=0.5,  # Only ~2-3 syllables worth
        seed=42,
    )

    # Should select fewer syllables to stay near target
    total_duration = sum(c.end - c.start for c in result.clips)
    assert total_duration <= 1.0  # Some slack, but well under 2.0

"""Tests for CLI argument parsing."""

import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

from glottisdale.cli import parse_args


def test_parse_local_files():
    args = parse_args(["file1.mp4", "file2.wav"])
    assert args.input_files == ["file1.mp4", "file2.wav"]


def test_parse_defaults():
    args = parse_args([])
    assert args.output_dir == "./glottisdale-output"
    assert args.syllables_per_word == "1-4"
    assert args.target_duration == 30.0
    assert args.crossfade == 30
    assert args.padding == 25
    assert args.phrase_pause == "400-700"
    assert args.sentence_pause == "800-1200"
    assert args.words_per_phrase == "3-5"
    assert args.phrases_per_sentence == "2-3"
    assert args.word_crossfade == 50
    assert args.whisper_model == "base"
    assert args.aligner == "auto"
    assert args.bfa_device == "cpu"
    assert args.seed is None


def test_parse_all_options():
    args = parse_args([
        "--output-dir", "/tmp/out",
        "--syllables-per-word", "3",
        "--target-duration", "30.0",
        "--crossfade", "0",
        "--padding", "50",
        "--phrase-pause", "100-500",
        "--sentence-pause", "600-900",
        "--words-per-phrase", "4-6",
        "--phrases-per-sentence", "3-4",
        "--word-crossfade", "30",
        "--whisper-model", "small",
        "--aligner", "default",
        "--seed", "42",
        "input.mp4",
    ])
    assert args.output_dir == "/tmp/out"
    assert args.syllables_per_word == "3"
    assert args.target_duration == 30.0
    assert args.crossfade == 0
    assert args.padding == 50
    assert args.phrase_pause == "100-500"
    assert args.sentence_pause == "600-900"
    assert args.words_per_phrase == "4-6"
    assert args.phrases_per_sentence == "3-4"
    assert args.word_crossfade == 30
    assert args.whisper_model == "small"
    assert args.seed == 42
    assert args.input_files == ["input.mp4"]


def test_backward_compat_syllables_per_clip():
    """--syllables-per-clip should still work as alias."""
    args = parse_args(["--syllables-per-clip", "2-4", "input.mp4"])
    assert args.syllables_per_word == "2-4"


def test_backward_compat_gap():
    """--gap should still work, mapping to phrase_pause."""
    args = parse_args(["--gap", "100-300", "input.mp4"])
    assert args.phrase_pause == "100-300"


def test_parse_slack_options():
    args = parse_args([
        "--source-channel", "#test-channel",
        "--dest-channel", "#output",
        "--max-videos", "3",
        "--dry-run",
        "--no-post",
    ])
    assert args.source_channel == "#test-channel"
    assert args.dest_channel == "#output"
    assert args.max_videos == 3
    assert args.dry_run is True
    assert args.no_post is True


def test_audio_polish_flags_defaults():
    args = parse_args([])
    assert args.noise_level == -40
    assert args.room_tone is True
    assert args.pitch_normalize is True
    assert args.pitch_range == 5
    assert args.breaths is True
    assert args.breath_probability == 0.6
    assert args.volume_normalize is True
    assert args.prosodic_dynamics is True


def test_audio_polish_flags_disabled():
    args = parse_args([
        "--no-room-tone", "--no-pitch-normalize", "--no-breaths",
        "--no-volume-normalize", "--no-prosodic-dynamics",
        "--noise-level", "0",
    ])
    assert args.noise_level == 0
    assert args.room_tone is False
    assert args.pitch_normalize is False
    assert args.breaths is False
    assert args.volume_normalize is False
    assert args.prosodic_dynamics is False


def test_cli_passes_audio_polish_to_process(tmp_path):
    """CLI local mode should pass all audio polish flags to process()."""
    from glottisdale.cli import main

    input_file = tmp_path / "test.wav"
    input_file.touch()

    mock_result = MagicMock()
    mock_result.transcript = "test"
    mock_result.clips = []
    mock_result.concatenated = MagicMock()
    mock_result.concatenated.name = "concatenated.wav"

    with patch("glottisdale.process") as mock_process:
        mock_process.return_value = mock_result
        main([
            str(input_file),
            "--output-dir", str(tmp_path / "out"),
            "--noise-level", "-30",
            "--no-pitch-normalize",
            "--pitch-range", "3",
            "--no-breaths",
            "--breath-probability", "0.4",
            "--no-room-tone",
            "--no-volume-normalize",
            "--no-prosodic-dynamics",
        ])

        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["noise_level_db"] == -30
        assert call_kwargs["pitch_normalize"] is False
        assert call_kwargs["pitch_range"] == 3
        assert call_kwargs["breaths"] is False
        assert call_kwargs["breath_probability"] == 0.4
        assert call_kwargs["room_tone"] is False
        assert call_kwargs["volume_normalize"] is False
        assert call_kwargs["prosodic_dynamics"] is False


def test_cli_passes_audio_polish_defaults_to_process(tmp_path):
    """CLI should pass default audio polish values when no flags are given."""
    from glottisdale.cli import main

    input_file = tmp_path / "test.wav"
    input_file.touch()

    mock_result = MagicMock()
    mock_result.transcript = "test"
    mock_result.clips = []
    mock_result.concatenated = MagicMock()
    mock_result.concatenated.name = "concatenated.wav"

    with patch("glottisdale.process") as mock_process:
        mock_process.return_value = mock_result
        main([str(input_file), "--output-dir", str(tmp_path / "out")])

        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["noise_level_db"] == -40
        assert call_kwargs["pitch_normalize"] is True
        assert call_kwargs["pitch_range"] == 5
        assert call_kwargs["breaths"] is True
        assert call_kwargs["breath_probability"] == 0.6
        assert call_kwargs["room_tone"] is True
        assert call_kwargs["volume_normalize"] is True
        assert call_kwargs["prosodic_dynamics"] is True


def test_stretch_repeat_flags_defaults():
    """All stretch/repeat flags should default to None/off."""
    args = parse_args([])
    assert args.speed is None
    assert args.random_stretch is None
    assert args.alternating_stretch is None
    assert args.boundary_stretch is None
    assert args.word_stretch is None
    assert args.stretch_factor == "2.0"
    assert args.repeat_weight is None
    assert args.repeat_count == "1-2"
    assert args.repeat_style == "exact"
    assert args.stutter is None
    assert args.stutter_count == "1-2"


def test_stretch_flags_set():
    args = parse_args([
        "--speed", "0.5",
        "--random-stretch", "0.3",
        "--alternating-stretch", "2",
        "--boundary-stretch", "1",
        "--word-stretch", "0.4",
        "--stretch-factor", "1.5-3.0",
    ])
    assert args.speed == 0.5
    assert args.random_stretch == 0.3
    assert args.alternating_stretch == 2
    assert args.boundary_stretch == 1
    assert args.word_stretch == 0.4
    assert args.stretch_factor == "1.5-3.0"


def test_repeat_flags_set():
    args = parse_args([
        "--repeat-weight", "0.2",
        "--repeat-count", "2-4",
        "--repeat-style", "resample",
    ])
    assert args.repeat_weight == 0.2
    assert args.repeat_count == "2-4"
    assert args.repeat_style == "resample"


def test_stutter_flags_set():
    args = parse_args([
        "--stutter", "0.3",
        "--stutter-count", "2-3",
    ])
    assert args.stutter == 0.3
    assert args.stutter_count == "2-3"


def test_cli_passes_stretch_repeat_to_process(tmp_path):
    """CLI should pass stretch/repeat flags to process()."""
    from glottisdale.cli import main

    input_file = tmp_path / "test.wav"
    input_file.touch()

    mock_result = MagicMock()
    mock_result.transcript = "test"
    mock_result.clips = []
    mock_result.concatenated = MagicMock()
    mock_result.concatenated.name = "concatenated.wav"

    with patch("glottisdale.process") as mock_process:
        mock_process.return_value = mock_result
        main([
            str(input_file),
            "--output-dir", str(tmp_path / "out"),
            "--random-stretch", "0.3",
            "--stretch-factor", "1.5-3.0",
            "--repeat-weight", "0.2",
            "--stutter", "0.4",
        ])

        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["random_stretch"] == 0.3
        assert call_kwargs["stretch_factor"] == "1.5-3.0"
        assert call_kwargs["repeat_weight"] == 0.2
        assert call_kwargs["stutter"] == 0.4

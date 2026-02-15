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
    assert args.target_duration == 10.0
    assert args.crossfade == 10
    assert args.padding == 25
    assert args.phrase_pause == "400-700"
    assert args.sentence_pause == "800-1200"
    assert args.words_per_phrase == "3-5"
    assert args.phrases_per_sentence == "2-3"
    assert args.word_crossfade == 25
    assert args.whisper_model == "base"
    assert args.aligner == "default"
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

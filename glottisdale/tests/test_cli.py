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
    assert args.syllables_per_clip == 1
    assert args.target_duration == 10.0
    assert args.crossfade == 10
    assert args.padding == 25
    assert args.gap == "50-200"
    assert args.whisper_model == "base"
    assert args.aligner == "default"
    assert args.seed is None


def test_parse_all_options():
    args = parse_args([
        "--output-dir", "/tmp/out",
        "--syllables-per-clip", "3",
        "--target-duration", "30.0",
        "--crossfade", "0",
        "--padding", "50",
        "--gap", "100-500",
        "--whisper-model", "small",
        "--aligner", "default",
        "--seed", "42",
        "input.mp4",
    ])
    assert args.output_dir == "/tmp/out"
    assert args.syllables_per_clip == 3
    assert args.target_duration == 30.0
    assert args.crossfade == 0
    assert args.padding == 50
    assert args.gap == "100-500"
    assert args.whisper_model == "small"
    assert args.seed == 42
    assert args.input_files == ["input.mp4"]


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

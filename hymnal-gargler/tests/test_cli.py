"""Tests for CLI."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_help():
    """--help should work."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "--help"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "hymnal" in result.stdout.lower() or "gargler" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_default_args():
    """Default argument values should be correct."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args([])
    assert args.target_duration == 40
    assert args.max_videos == 5
    assert args.whisper_model == "base"
    assert args.drift_range == 2.0
    assert args.vibrato is True
    assert args.chorus is True
    assert not args.dry_run
    assert not args.no_post
    assert args.seed is None
    assert args.midi is None
    assert args.audio is None
    assert args.output_dir == Path("./hymnal-gargler-output")
    assert args.source_channel == "midieval"
    assert args.video_channel == "sample-sale"
    assert args.dest_channel == "glottisdale"


def test_local_mode_requires_both_midi_and_audio():
    """Providing --midi without --audio should fail."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "--midi", "/tmp/midi"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode != 0
    assert "audio" in result.stderr.lower()


def test_local_mode_requires_both_audio_and_midi():
    """Providing --audio without --midi should fail."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "--audio", "/tmp/a.wav"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode != 0
    assert "midi" in result.stderr.lower()


def test_vibrato_disabled():
    """--no-vibrato should disable vibrato."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["--no-vibrato"])
    assert args.vibrato is False


def test_chorus_disabled():
    """--no-chorus should disable chorus."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["--no-chorus"])
    assert args.chorus is False


def test_seed_flag():
    """--seed should set the RNG seed."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["--seed", "42"])
    assert args.seed == 42


def test_dry_run_flag():
    """--dry-run should be set."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True


def test_custom_channels():
    """Channel flags should override defaults."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "--source-channel", "my-midi",
        "--video-channel", "my-videos",
        "--dest-channel", "my-output",
    ])
    assert args.source_channel == "my-midi"
    assert args.video_channel == "my-videos"
    assert args.dest_channel == "my-output"


def test_whisper_model_choices():
    """--whisper-model should accept valid choices."""
    from cli import build_parser
    parser = build_parser()
    for model in ["tiny", "base", "small", "medium"]:
        args = parser.parse_args(["--whisper-model", model])
        assert args.whisper_model == model


def test_multiple_audio_files():
    """--audio should accept multiple files."""
    from cli import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "--midi", "/tmp/midi",
        "--audio", "/tmp/a.wav", "/tmp/b.wav", "/tmp/c.wav",
    ])
    assert len(args.audio) == 3
    assert args.audio[0] == Path("/tmp/a.wav")
    assert args.audio[2] == Path("/tmp/c.wav")

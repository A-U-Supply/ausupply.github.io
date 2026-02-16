"""Tests for MIDI extender (Python wrapper)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from extender import extend_midi, _fallback_loop


def test_fallback_loop_copies_files(tmp_path):
    """Fallback should copy original files to output dir."""
    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        (tmp_path / name).write_bytes(b"MThd dummy")

    output = tmp_path / "output"
    output.mkdir()
    _fallback_loop(
        tmp_path / "melody.mid",
        tmp_path / "drums.mid",
        tmp_path / "bass.mid",
        tmp_path / "chords.mid",
        output,
    )
    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        assert (output / name).exists()


@patch("extender.subprocess.run")
def test_extend_midi_calls_node(mock_run, tmp_path):
    """Should call node with correct params."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='{"melody_notes": 50}',
        stderr="",
    )
    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        (tmp_path / name).write_bytes(b"MThd")

    result = extend_midi(
        tmp_path / "melody.mid",
        tmp_path / "drums.mid",
        tmp_path / "bass.mid",
        tmp_path / "chords.mid",
        tmp_path / "output",
        target_duration=40.0,
        tempo=120,
    )
    assert mock_run.called
    call_args = mock_run.call_args
    assert "node" in call_args[0][0]
    assert result["melody_notes"] == 50


@patch("extender.subprocess.run")
def test_extend_midi_falls_back_on_failure(mock_run, tmp_path):
    """Should fall back to copying files if node fails."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        (tmp_path / name).write_bytes(b"MThd")
    output = tmp_path / "output"
    output.mkdir()

    result = extend_midi(
        tmp_path / "melody.mid",
        tmp_path / "drums.mid",
        tmp_path / "bass.mid",
        tmp_path / "chords.mid",
        output,
        target_duration=40.0,
    )
    assert result.get("fallback") is True

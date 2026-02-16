"""Tests for mixer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mixer import build_mix_command


def test_build_mix_command():
    """Mix command should combine vocal and MIDI backing."""
    cmd = build_mix_command(
        vocal_path=Path("/tmp/vocal.wav"),
        midi_wav_path=Path("/tmp/midi.wav"),
        output_path=Path("/tmp/mix.wav"),
        vocal_weight=0.8,
        midi_weight=0.5,
    )
    cmd_str = " ".join(str(c) for c in cmd)
    assert "ffmpeg" in cmd[0]
    assert "/tmp/vocal.wav" in cmd_str
    assert "/tmp/midi.wav" in cmd_str
    assert "amix" in cmd_str

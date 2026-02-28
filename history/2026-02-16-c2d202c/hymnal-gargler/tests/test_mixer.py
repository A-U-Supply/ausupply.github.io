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
    )
    cmd_str = " ".join(str(c) for c in cmd)
    assert "ffmpeg" in cmd[0]
    assert "/tmp/vocal.wav" in cmd_str
    assert "/tmp/midi.wav" in cmd_str
    assert "amix" in cmd_str
    assert "volume" in cmd_str
    assert "normalize=0" in cmd_str


def test_build_mix_command_custom_levels():
    """Custom dB levels should appear in the filter."""
    cmd = build_mix_command(
        vocal_path=Path("/tmp/vocal.wav"),
        midi_wav_path=Path("/tmp/midi.wav"),
        output_path=Path("/tmp/mix.wav"),
        vocal_db=3,
        midi_db=-18,
    )
    cmd_str = " ".join(str(c) for c in cmd)
    assert "volume=3dB" in cmd_str
    assert "volume=-18dB" in cmd_str

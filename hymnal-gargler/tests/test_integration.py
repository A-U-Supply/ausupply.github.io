"""Integration tests for Hymnal Gargler pipeline."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for real test data
PUKE_BOX_DIR = Path(__file__).parent.parent.parent / "puke-box"
HAS_MIDI_DATA = any(PUKE_BOX_DIR.glob("*/melody.mid"))


def _find_midi_dir() -> Path | None:
    """Find the first puke-box directory with MIDI files."""
    for d in sorted(PUKE_BOX_DIR.iterdir(), reverse=True):
        if d.is_dir() and (d / "melody.mid").exists():
            return d
    return None


def test_cli_help():
    """bot.py --help should work end-to-end."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "bot.py"), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Hymnal Gargler" in result.stdout


def test_cli_requires_slack_token_for_slack_mode():
    """Running without --midi/--audio should require SLACK_BOT_TOKEN."""
    env = {"PATH": "/usr/bin:/bin"}  # No SLACK_BOT_TOKEN
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "bot.py")],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode != 0
    assert "SLACK_BOT_TOKEN" in result.stderr


@pytest.mark.skipif(not HAS_MIDI_DATA, reason="No puke-box MIDI data available")
def test_midi_parser_with_real_files():
    """Parse real MIDI files from puke-box."""
    from midi_parser import parse_midi

    midi_dir = _find_midi_dir()
    assert midi_dir is not None

    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        path = midi_dir / name
        if path.exists():
            track = parse_midi(path)
            assert track.tempo > 0
            assert track.total_duration > 0


@pytest.mark.skipif(not HAS_MIDI_DATA, reason="No puke-box MIDI data available")
def test_vocal_mapper_with_real_melody():
    """Plan note mapping with a real melody track."""
    from midi_parser import parse_midi
    from vocal_mapper import plan_note_mapping

    midi_dir = _find_midi_dir()
    track = parse_midi(midi_dir / "melody.mid")

    if not track.notes:
        pytest.skip("Melody has no notes")

    mappings = plan_note_mapping(track.notes, pool_size=10, seed=42)
    assert len(mappings) == len(track.notes)
    for m in mappings:
        assert m.duration_class in ("short", "medium", "long")
        assert len(m.syllable_indices) >= 1


def test_extender_fallback():
    """Extender fallback should copy files when Node.js fails."""
    import tempfile
    import shutil
    from extender import extend_midi

    midi_dir = None
    if HAS_MIDI_DATA:
        midi_dir = _find_midi_dir()

    if not midi_dir:
        # Create minimal MIDI files for testing
        import pretty_midi

        midi_dir = Path(tempfile.mkdtemp()) / "midi"
        midi_dir.mkdir()
        for name in ["melody", "drums", "bass", "chords"]:
            pm = pretty_midi.PrettyMIDI()
            inst = pretty_midi.Instrument(program=0)
            inst.notes.append(pretty_midi.Note(
                velocity=100, pitch=60, start=0.0, end=1.0,
            ))
            pm.instruments.append(inst)
            pm.write(str(midi_dir / f"{name}.mid"))

    with tempfile.TemporaryDirectory() as out_dir:
        # This will fail (no node_modules installed in test env) and fall back
        result = extend_midi(
            melody_path=midi_dir / "melody.mid",
            drums_path=midi_dir / "drums.mid",
            bass_path=midi_dir / "bass.mid",
            chords_path=midi_dir / "chords.mid",
            output_dir=Path(out_dir),
        )
        # Should return fallback result
        assert isinstance(result, dict)
        # Fallback copies files
        if result.get("fallback"):
            for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
                assert (Path(out_dir) / name).exists()

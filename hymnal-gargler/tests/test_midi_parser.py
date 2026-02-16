"""Tests for MIDI parser."""
import sys
import tempfile
from pathlib import Path

import pretty_midi

sys.path.insert(0, str(Path(__file__).parent.parent))
from midi_parser import parse_midi, Note


def _make_test_midi(notes, tempo=120, program=0, is_drum=False):
    """Create a MIDI file with the given notes for testing."""
    mid = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for pitch, start, end, velocity in notes:
        inst.notes.append(pretty_midi.Note(
            velocity=velocity, pitch=pitch, start=start, end=end
        ))
    mid.instruments.append(inst)
    path = Path(tempfile.mktemp(suffix=".mid"))
    mid.write(str(path))
    return path


def test_parse_midi_extracts_notes():
    path = _make_test_midi([
        (60, 0.0, 0.5, 100),
        (64, 0.5, 1.0, 90),
        (67, 1.0, 1.5, 80),
    ], tempo=120)
    try:
        result = parse_midi(path)
        assert len(result.notes) == 3
        assert result.notes[0].pitch == 60
        assert result.notes[0].start == 0.0
        assert result.notes[0].end == 0.5
        assert result.notes[0].velocity == 100
        assert result.tempo == 120
        assert result.total_duration > 0
    finally:
        path.unlink(missing_ok=True)


def test_parse_midi_empty_file():
    path = _make_test_midi([], tempo=100)
    try:
        result = parse_midi(path)
        assert len(result.notes) == 0
        assert result.tempo == 100
    finally:
        path.unlink(missing_ok=True)


def test_note_duration():
    note = Note(pitch=60, start=0.5, end=1.25, velocity=100)
    assert note.duration == 0.75

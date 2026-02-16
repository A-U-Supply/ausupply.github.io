"""Tests for vocal mapper."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from vocal_mapper import (
    compute_target_pitch,
    classify_note_duration,
    plan_note_mapping,
    NoteMapping,
)
from midi_parser import Note


def test_compute_target_pitch_exact():
    """With drift=0, target matches note exactly."""
    # A4 = 440 Hz, source at 220 Hz = A3
    shift = compute_target_pitch(
        note_midi=69,  # A4
        source_f0=220.0,
        drift_semitones=0,
    )
    expected = 12 * math.log2(440.0 / 220.0)  # 12 semitones
    assert abs(shift - expected) < 0.01


def test_compute_target_pitch_with_drift():
    """Drift should offset the target."""
    shift_no_drift = compute_target_pitch(69, 220.0, drift_semitones=0)
    shift_with_drift = compute_target_pitch(69, 220.0, drift_semitones=2)
    # The shift should differ by the drift amount
    assert abs(abs(shift_with_drift - shift_no_drift) - 2) < 0.01


def test_classify_short_note():
    assert classify_note_duration(0.1) == "short"
    assert classify_note_duration(0.15) == "short"


def test_classify_medium_note():
    assert classify_note_duration(0.3) == "medium"
    assert classify_note_duration(0.8) == "medium"


def test_classify_long_note():
    assert classify_note_duration(1.5) == "long"


def test_plan_note_mapping_assigns_syllables():
    notes = [
        Note(pitch=60, start=0.0, end=0.5, velocity=100),
        Note(pitch=64, start=0.5, end=1.0, velocity=100),
        Note(pitch=67, start=1.0, end=2.0, velocity=100),
    ]
    # 5 available syllables
    pool_size = 5
    mappings = plan_note_mapping(notes, pool_size, seed=42)
    assert len(mappings) == 3
    # Each mapping should have syllable indices within range
    for m in mappings:
        for idx in m.syllable_indices:
            assert 0 <= idx < pool_size

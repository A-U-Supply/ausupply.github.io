"""Tests for syllable preparation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from syllable_prep import (
    compute_pitch_shifts,
    NormalizedSyllable,
)


def test_compute_pitch_shifts_to_median():
    """Syllables should be shifted to the median F0."""
    f0s = [100.0, 200.0, 150.0]  # median = 150
    shifts = compute_pitch_shifts(f0s)
    # 100 -> 150: +7.02 semitones (12 * log2(150/100))
    # 200 -> 150: -4.98 semitones
    # 150 -> 150: 0 semitones
    assert abs(shifts[2]) < 0.01  # median stays unchanged
    assert shifts[0] > 0  # below median shifts up
    assert shifts[1] < 0  # above median shifts down


def test_compute_pitch_shifts_skips_none():
    """Unvoiced syllables (None F0) get 0 shift."""
    f0s = [100.0, None, 200.0]
    shifts = compute_pitch_shifts(f0s)
    assert shifts[1] == 0.0


def test_normalized_syllable_dataclass():
    syl = NormalizedSyllable(
        clip_path=Path("/tmp/clip.wav"),
        f0=150.0,
        duration=0.5,
        phonemes=["AH0"],
        word="test",
    )
    assert syl.duration == 0.5
    assert syl.f0 == 150.0

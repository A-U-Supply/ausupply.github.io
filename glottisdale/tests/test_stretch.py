"""Tests for stretch selection logic and config parsing."""

import random
import pytest

from glottisdale.stretch import (
    StretchConfig,
    parse_stretch_factor,
    should_stretch_syllable,
    resolve_stretch_factor,
    apply_stutter,
    apply_word_repeat,
    parse_count_range,
)
from pathlib import Path
from glottisdale.types import Clip, Syllable, Phoneme


class TestParseStretchFactor:
    def test_single_value(self):
        assert parse_stretch_factor("2.0") == (2.0, 2.0)

    def test_range(self):
        assert parse_stretch_factor("1.5-3.0") == (1.5, 3.0)

    def test_integer(self):
        assert parse_stretch_factor("2") == (2.0, 2.0)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_stretch_factor("abc")


class TestResolveStretchFactor:
    def test_fixed_factor(self):
        rng = random.Random(42)
        factor = resolve_stretch_factor((2.0, 2.0), rng)
        assert factor == 2.0

    def test_range_factor_within_bounds(self):
        rng = random.Random(42)
        for _ in range(100):
            factor = resolve_stretch_factor((1.5, 3.0), rng)
            assert 1.5 <= factor <= 3.0


class TestShouldStretchSyllable:
    def test_random_stretch_selects_probabilistically(self):
        rng = random.Random(42)
        config = StretchConfig(random_stretch=0.5)
        selected = sum(
            should_stretch_syllable(i, 0, 3, rng, config)
            for i in range(1000)
        )
        # ~50% should be selected, allow wide margin
        assert 350 < selected < 650

    def test_alternating_stretch_every_other(self):
        rng = random.Random(42)
        config = StretchConfig(alternating_stretch=2)
        results = [
            should_stretch_syllable(i, 0, 3, rng, config)
            for i in range(6)
        ]
        assert results == [True, False, True, False, True, False]

    def test_alternating_stretch_every_third(self):
        rng = random.Random(42)
        config = StretchConfig(alternating_stretch=3)
        results = [
            should_stretch_syllable(i, 0, 3, rng, config)
            for i in range(6)
        ]
        assert results == [True, False, False, True, False, False]

    def test_boundary_stretch_first_and_last(self):
        rng = random.Random(42)
        config = StretchConfig(boundary_stretch=1)
        # 4-syllable word: indices 0, 1, 2, 3
        results = [
            should_stretch_syllable(i, syl_idx, 4, rng, config)
            for i, syl_idx in enumerate(range(4))
        ]
        assert results == [True, False, False, True]

    def test_boundary_stretch_all_selected_short_word(self):
        """For a 2-syllable word with boundary=1, both syllables selected."""
        rng = random.Random(42)
        config = StretchConfig(boundary_stretch=1)
        results = [
            should_stretch_syllable(i, syl_idx, 2, rng, config)
            for i, syl_idx in enumerate(range(2))
        ]
        assert results == [True, True]

    def test_no_modes_active_returns_false(self):
        rng = random.Random(42)
        config = StretchConfig()
        assert not should_stretch_syllable(0, 0, 3, rng, config)

    def test_combined_modes_or_logic(self):
        """A syllable selected by ANY active mode gets stretched."""
        rng = random.Random(42)
        config = StretchConfig(alternating_stretch=2, boundary_stretch=1)
        # 4-syllable word: alternating selects 0,2; boundary selects 0,3
        # Union: 0, 2, 3
        results = [
            should_stretch_syllable(i, syl_idx, 4, rng, config)
            for i, syl_idx in enumerate(range(4))
        ]
        assert results == [True, False, True, True]


class TestParseCountRange:
    def test_single_value(self):
        assert parse_count_range("2") == (2, 2)

    def test_range(self):
        assert parse_count_range("1-3") == (1, 3)


class TestApplyStutter:
    def test_no_stutter_when_probability_zero(self):
        paths = [Path("a.wav"), Path("b.wav"), Path("c.wav")]
        rng = random.Random(42)
        result = apply_stutter(paths, probability=0.0, count_range=(1, 2), rng=rng)
        assert result == paths

    def test_all_stutter_when_probability_one(self):
        paths = [Path("a.wav"), Path("b.wav")]
        rng = random.Random(42)
        result = apply_stutter(paths, probability=1.0, count_range=(1, 1), rng=rng)
        # Each path should appear twice (original + 1 copy)
        assert len(result) == 4
        assert result == [Path("a.wav"), Path("a.wav"),
                          Path("b.wav"), Path("b.wav")]

    def test_stutter_count_range(self):
        paths = [Path("a.wav")]
        rng = random.Random(42)
        result = apply_stutter(paths, probability=1.0, count_range=(2, 2), rng=rng)
        # Original + 2 copies = 3
        assert len(result) == 3
        assert all(p == Path("a.wav") for p in result)

    def test_stutter_probabilistic(self):
        paths = [Path(f"{i}.wav") for i in range(100)]
        rng = random.Random(42)
        result = apply_stutter(paths, probability=0.3, count_range=(1, 1), rng=rng)
        # Should have more than 100 (some duplicated) but not all
        assert len(result) > 100
        assert len(result) < 200

    def test_stutter_preserves_order(self):
        paths = [Path("a.wav"), Path("b.wav"), Path("c.wav")]
        rng = random.Random(42)
        result = apply_stutter(paths, probability=1.0, count_range=(1, 1), rng=rng)
        # Should be a, a, b, b, c, c — originals in order with copies after each
        assert result[0] == Path("a.wav")
        assert result[1] == Path("a.wav")
        assert result[2] == Path("b.wav")
        assert result[3] == Path("b.wav")
        assert result[4] == Path("c.wav")
        assert result[5] == Path("c.wav")


def _make_clip(name: str) -> Clip:
    """Helper to create a Clip with a given output path name."""
    syl = Syllable([Phoneme("AH0", 0.0, 0.1)], 0.0, 0.1, "test", 0)
    return Clip(syllables=[syl], start=0.0, end=0.1,
                source="test", output_path=Path(f"{name}.wav"))


class TestApplyWordRepeat:
    def test_no_repeat_when_probability_zero(self):
        words = [_make_clip("a"), _make_clip("b")]
        rng = random.Random(42)
        result = apply_word_repeat(words, probability=0.0,
                                   count_range=(1, 1), style="exact", rng=rng)
        assert len(result) == 2

    def test_all_repeat_exact(self):
        words = [_make_clip("a"), _make_clip("b")]
        rng = random.Random(42)
        result = apply_word_repeat(words, probability=1.0,
                                   count_range=(1, 1), style="exact", rng=rng)
        assert len(result) == 4
        # Each word followed by its duplicate
        assert result[0].output_path == result[1].output_path
        assert result[2].output_path == result[3].output_path

    def test_repeat_count_range(self):
        words = [_make_clip("a")]
        rng = random.Random(42)
        result = apply_word_repeat(words, probability=1.0,
                                   count_range=(3, 3), style="exact", rng=rng)
        # Original + 3 copies = 4
        assert len(result) == 4

    def test_preserves_order(self):
        words = [_make_clip("a"), _make_clip("b"), _make_clip("c")]
        rng = random.Random(42)
        result = apply_word_repeat(words, probability=1.0,
                                   count_range=(1, 1), style="exact", rng=rng)
        # a, a, b, b, c, c
        paths = [c.output_path.stem for c in result]
        assert paths == ["a", "a", "b", "b", "c", "c"]

    def test_probabilistic_repeat(self):
        words = [_make_clip(f"w{i}") for i in range(100)]
        rng = random.Random(42)
        result = apply_word_repeat(words, probability=0.3,
                                   count_range=(1, 1), style="exact", rng=rng)
        assert len(result) > 100
        assert len(result) < 200

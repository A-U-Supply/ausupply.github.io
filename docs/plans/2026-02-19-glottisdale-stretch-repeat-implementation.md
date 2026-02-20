# Glottisdale Time Stretch & Word Repeat Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add time-stretching (5 selection modes) and word/syllable repetition to Glottisdale's assembly pipeline.

**Architecture:** New `stretch.py` module for stretch selection logic and `time_stretch_clip()` in `audio.py`. Stutter/repeat logic lives in `__init__.py` as transform passes between existing pipeline stages. All features off by default, pitch-preserving stretch via ffmpeg rubberband filter.

**Tech Stack:** ffmpeg rubberband filter (requires `librubberband-dev`), existing ffmpeg/ffprobe infrastructure in `audio.py`.

---

### Task 1: Add `time_stretch_clip()` to `audio.py`

**Files:**
- Modify: `glottisdale/src/glottisdale/audio.py:243-274` (after `pitch_shift_clip`)
- Test: `glottisdale/tests/test_audio.py`

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_audio.py`:

```python
from glottisdale.audio import time_stretch_clip


def test_time_stretch_doubles_duration(tmp_path):
    """Stretching by 2.0 should approximately double the duration."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "stretched.wav"
    time_stretch_clip(clip, out, factor=2.0)
    assert out.exists()
    stretched_dur = get_duration(out)
    assert abs(stretched_dur - 2.0) < 0.3  # ~2x original 1.0s


def test_time_stretch_halves_duration(tmp_path):
    """Stretching by 0.5 should approximately halve the duration."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "stretched.wav"
    time_stretch_clip(clip, out, factor=0.5)
    assert out.exists()
    stretched_dur = get_duration(out)
    assert abs(stretched_dur - 0.5) < 0.2


def test_time_stretch_identity(tmp_path):
    """Factor 1.0 should copy without processing."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "stretched.wav"
    time_stretch_clip(clip, out, factor=1.0)
    assert out.exists()
    original_dur = get_duration(clip)
    stretched_dur = get_duration(out)
    assert abs(stretched_dur - original_dur) < 0.05


def test_time_stretch_no_rubberband_fallback(tmp_path, monkeypatch):
    """If rubberband not available, should copy the file and log warning."""
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    # Simulate rubberband not installed by making ffmpeg fail with rubberband filter
    import subprocess
    original_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if any("rubberband" in str(c) for c in cmd):
            result = subprocess.CompletedProcess(cmd, 1, "", "No such filter: 'rubberband'")
            result.check_returncode()  # raises CalledProcessError
        return original_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = tmp_path / "stretched.wav"
    # Should not raise, just copy
    time_stretch_clip(clip, out, factor=2.0)
    assert out.exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd glottisdale && python -m pytest tests/test_audio.py::test_time_stretch_doubles_duration tests/test_audio.py::test_time_stretch_halves_duration tests/test_audio.py::test_time_stretch_identity tests/test_audio.py::test_time_stretch_no_rubberband_fallback -v`
Expected: FAIL — `ImportError: cannot import name 'time_stretch_clip'`

**Step 3: Write minimal implementation**

Add to `glottisdale/src/glottisdale/audio.py` after `pitch_shift_clip()`:

```python
def time_stretch_clip(input_path: Path, output_path: Path, factor: float) -> Path:
    """Time-stretch a WAV clip by factor. Pitch-preserving via rubberband.

    factor > 1.0 = slower (longer), factor < 1.0 = faster (shorter).
    factor = 1.0 = no-op (copy). Falls back to copy if rubberband unavailable.
    """
    if abs(factor - 1.0) < 0.01:
        shutil.copy2(input_path, output_path)
        return output_path

    # rubberband tempo is inverse: factor 2.0 (twice as long) = tempo 0.5
    tempo = 1.0 / factor

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"rubberband=tempo={tempo:.4f}",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60).check_returncode()
    except (subprocess.CalledProcessError, FileNotFoundError):
        import logging
        logging.getLogger("glottisdale").warning(
            "rubberband filter unavailable, skipping time stretch"
        )
        shutil.copy2(input_path, output_path)
    return output_path
```

**Step 4: Run tests to verify they pass**

Run: `cd glottisdale && python -m pytest tests/test_audio.py -k "time_stretch" -v`
Expected: PASS (all 4 tests). Note: `test_time_stretch_doubles_duration` and `test_time_stretch_halves_duration` require rubberband installed locally. If not installed, the fallback test should still pass but the duration-check tests will fail. Install with `brew install rubberband` on macOS.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/audio.py glottisdale/tests/test_audio.py
git commit -m "feat(glottisdale): add time_stretch_clip with rubberband fallback"
```

---

### Task 2: Add `stretch.py` module — stretch selection logic

**Files:**
- Create: `glottisdale/src/glottisdale/stretch.py`
- Test: `glottisdale/tests/test_stretch.py`

**Step 1: Write the failing tests**

Create `glottisdale/tests/test_stretch.py`:

```python
"""Tests for stretch selection logic and config parsing."""

import random
import pytest

from glottisdale.stretch import (
    StretchConfig,
    parse_stretch_factor,
    should_stretch_syllable,
    resolve_stretch_factor,
)


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
```

**Step 2: Run tests to verify they fail**

Run: `cd glottisdale && python -m pytest tests/test_stretch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'glottisdale.stretch'`

**Step 3: Write minimal implementation**

Create `glottisdale/src/glottisdale/stretch.py`:

```python
"""Stretch selection logic for time-stretch features."""

import random
from dataclasses import dataclass


@dataclass
class StretchConfig:
    """Configuration for which syllables/words get stretched."""
    random_stretch: float | None = None       # probability 0-1
    alternating_stretch: int | None = None    # every Nth syllable
    boundary_stretch: int | None = None       # first/last N in each word
    word_stretch: float | None = None         # probability 0-1 for whole words
    stretch_factor: tuple[float, float] = (2.0, 2.0)  # (min, max) range


def parse_stretch_factor(s: str) -> tuple[float, float]:
    """Parse stretch factor string: '2.0' or '1.5-3.0' into (min, max)."""
    if "-" in s:
        # Check if it's a negative number vs a range
        parts = s.split("-")
        # Filter out empty strings from leading minus
        parts = [p for p in parts if p]
        if len(parts) == 2 and not s.startswith("-"):
            return float(parts[0]), float(parts[1])
    return float(s), float(s)


def resolve_stretch_factor(
    factor_range: tuple[float, float], rng: random.Random
) -> float:
    """Pick a stretch factor from the range. Fixed if min==max."""
    if factor_range[0] == factor_range[1]:
        return factor_range[0]
    return rng.uniform(factor_range[0], factor_range[1])


def should_stretch_syllable(
    syllable_index: int,
    word_syllable_index: int,
    word_syllable_count: int,
    rng: random.Random,
    config: StretchConfig,
) -> bool:
    """Determine if a syllable should be stretched based on active modes.

    Returns True if ANY active mode selects this syllable.
    """
    if config.random_stretch is not None:
        if rng.random() < config.random_stretch:
            return True

    if config.alternating_stretch is not None:
        if syllable_index % config.alternating_stretch == 0:
            return True

    if config.boundary_stretch is not None:
        n = config.boundary_stretch
        if (word_syllable_index < n
                or word_syllable_index >= word_syllable_count - n):
            return True

    return False
```

**Step 4: Run tests to verify they pass**

Run: `cd glottisdale && python -m pytest tests/test_stretch.py -v`
Expected: PASS (all 11 tests)

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/stretch.py glottisdale/tests/test_stretch.py
git commit -m "feat(glottisdale): add stretch selection logic module"
```

---

### Task 3: Add stutter logic

**Files:**
- Modify: `glottisdale/src/glottisdale/stretch.py`
- Test: `glottisdale/tests/test_stretch.py`

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_stretch.py`:

```python
from glottisdale.stretch import apply_stutter, parse_count_range
from pathlib import Path


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
```

**Step 2: Run tests to verify they fail**

Run: `cd glottisdale && python -m pytest tests/test_stretch.py::TestParseCountRange tests/test_stretch.py::TestApplyStutter -v`
Expected: FAIL — `ImportError: cannot import name 'apply_stutter'`

**Step 3: Write minimal implementation**

Add to `glottisdale/src/glottisdale/stretch.py`:

```python
from pathlib import Path


def parse_count_range(s: str) -> tuple[int, int]:
    """Parse count string: '2' or '1-3' into (min, max)."""
    if "-" in s:
        parts = s.split("-", 1)
        return int(parts[0]), int(parts[1])
    val = int(s)
    return val, val


def apply_stutter(
    syllable_paths: list[Path],
    probability: float,
    count_range: tuple[int, int],
    rng: random.Random,
) -> list[Path]:
    """Duplicate syllable clips in-place for stuttering effect.

    Returns new list with stuttered syllables repeated.
    """
    result = []
    for path in syllable_paths:
        result.append(path)
        if rng.random() < probability:
            n = rng.randint(count_range[0], count_range[1])
            result.extend([path] * n)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd glottisdale && python -m pytest tests/test_stretch.py -v`
Expected: PASS (all tests including previous ones)

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/stretch.py glottisdale/tests/test_stretch.py
git commit -m "feat(glottisdale): add stutter and count range parsing"
```

---

### Task 4: Add word repeat logic

**Files:**
- Modify: `glottisdale/src/glottisdale/stretch.py`
- Test: `glottisdale/tests/test_stretch.py`

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_stretch.py`:

```python
from glottisdale.stretch import apply_word_repeat
from glottisdale.types import Clip, Syllable, Phoneme


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
```

**Step 2: Run tests to verify they fail**

Run: `cd glottisdale && python -m pytest tests/test_stretch.py::TestApplyWordRepeat -v`
Expected: FAIL — `ImportError: cannot import name 'apply_word_repeat'`

**Step 3: Write minimal implementation**

Add to `glottisdale/src/glottisdale/stretch.py`:

```python
from glottisdale.types import Clip


def apply_word_repeat(
    words: list[Clip],
    probability: float,
    count_range: tuple[int, int],
    style: str,
    rng: random.Random,
) -> list[Clip]:
    """Duplicate words in the word list for repetition effect.

    style='exact': duplicate the same Clip (same WAV file).
    style='resample': not implemented here — caller handles re-assembly.
    Returns new list with repeated words inserted after originals.
    """
    result = []
    for word in words:
        result.append(word)
        if rng.random() < probability:
            n = rng.randint(count_range[0], count_range[1])
            if style == "exact":
                result.extend([word] * n)
            # 'resample' handled by caller in pipeline
    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd glottisdale && python -m pytest tests/test_stretch.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/stretch.py glottisdale/tests/test_stretch.py
git commit -m "feat(glottisdale): add word repeat logic"
```

---

### Task 5: Add CLI flags

**Files:**
- Modify: `glottisdale/src/glottisdale/cli.py:88-89` (before `args = parser.parse_args(argv)`)
- Test: `glottisdale/tests/test_cli.py`

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_cli.py`:

```python
def test_stretch_repeat_flags_defaults():
    """All stretch/repeat flags should default to None/off."""
    args = parse_args([])
    assert args.speed is None
    assert args.random_stretch is None
    assert args.alternating_stretch is None
    assert args.boundary_stretch is None
    assert args.word_stretch is None
    assert args.stretch_factor == "2.0"
    assert args.repeat_weight is None
    assert args.repeat_count == "1-2"
    assert args.repeat_style == "exact"
    assert args.stutter is None
    assert args.stutter_count == "1-2"


def test_stretch_flags_set():
    args = parse_args([
        "--speed", "0.5",
        "--random-stretch", "0.3",
        "--alternating-stretch", "2",
        "--boundary-stretch", "1",
        "--word-stretch", "0.4",
        "--stretch-factor", "1.5-3.0",
    ])
    assert args.speed == 0.5
    assert args.random_stretch == 0.3
    assert args.alternating_stretch == 2
    assert args.boundary_stretch == 1
    assert args.word_stretch == 0.4
    assert args.stretch_factor == "1.5-3.0"


def test_repeat_flags_set():
    args = parse_args([
        "--repeat-weight", "0.2",
        "--repeat-count", "2-4",
        "--repeat-style", "resample",
    ])
    assert args.repeat_weight == 0.2
    assert args.repeat_count == "2-4"
    assert args.repeat_style == "resample"


def test_stutter_flags_set():
    args = parse_args([
        "--stutter", "0.3",
        "--stutter-count", "2-3",
    ])
    assert args.stutter == 0.3
    assert args.stutter_count == "2-3"


def test_cli_passes_stretch_repeat_to_process(tmp_path):
    """CLI should pass stretch/repeat flags to process()."""
    from glottisdale.cli import main

    input_file = tmp_path / "test.wav"
    input_file.touch()

    mock_result = MagicMock()
    mock_result.transcript = "test"
    mock_result.clips = []
    mock_result.concatenated = MagicMock()
    mock_result.concatenated.name = "concatenated.wav"

    with patch("glottisdale.process") as mock_process:
        mock_process.return_value = mock_result
        main([
            str(input_file),
            "--output-dir", str(tmp_path / "out"),
            "--random-stretch", "0.3",
            "--stretch-factor", "1.5-3.0",
            "--repeat-weight", "0.2",
            "--stutter", "0.4",
        ])

        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["random_stretch"] == 0.3
        assert call_kwargs["stretch_factor"] == "1.5-3.0"
        assert call_kwargs["repeat_weight"] == 0.2
        assert call_kwargs["stutter"] == 0.4
```

**Step 2: Run tests to verify they fail**

Run: `cd glottisdale && python -m pytest tests/test_cli.py::test_stretch_repeat_flags_defaults tests/test_cli.py::test_stretch_flags_set tests/test_cli.py::test_repeat_flags_set tests/test_cli.py::test_stutter_flags_set tests/test_cli.py::test_cli_passes_stretch_repeat_to_process -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'speed'`

**Step 3: Write minimal implementation**

Add to `glottisdale/src/glottisdale/cli.py` after the audio polish options block (line 88), before `args = parser.parse_args(argv)`:

```python
    # Time stretch options (all off by default)
    parser.add_argument("--speed", type=float, default=None,
                        help="Global speed factor: 0.5=half speed, 2.0=double (default: off)")
    parser.add_argument("--random-stretch", type=float, default=None,
                        help="Probability (0-1) that a syllable gets stretched (default: off)")
    parser.add_argument("--alternating-stretch", type=int, default=None,
                        help="Stretch every Nth syllable (default: off)")
    parser.add_argument("--boundary-stretch", type=int, default=None,
                        help="Stretch first/last N syllables per word (default: off)")
    parser.add_argument("--word-stretch", type=float, default=None,
                        help="Probability (0-1) that all syllables in a word get stretched (default: off)")
    parser.add_argument("--stretch-factor", default="2.0",
                        help="Stretch amount: '2.0' or '1.5-3.0' for random range (default: 2.0)")

    # Word repeat options (all off by default)
    parser.add_argument("--repeat-weight", type=float, default=None,
                        help="Probability (0-1) that a word gets repeated (default: off)")
    parser.add_argument("--repeat-count", default="1-2",
                        help="Extra copies per repeated word: '2' or '1-3' (default: 1-2)")
    parser.add_argument("--repeat-style", default="exact",
                        choices=["exact", "resample"],
                        help="Repeat style: exact (duplicate WAV) or resample (default: exact)")

    # Stutter options (all off by default)
    parser.add_argument("--stutter", type=float, default=None,
                        help="Probability (0-1) that a syllable gets stuttered (default: off)")
    parser.add_argument("--stutter-count", default="1-2",
                        help="Extra copies of stuttered syllable: '2' or '1-3' (default: 1-2)")
```

Also update both `process()` call sites in `cli.py` (local mode at lines 120-144 and Slack mode at lines 187-211) to pass the new params:

```python
            # Add these kwargs to both process() calls:
            speed=args.speed,
            random_stretch=args.random_stretch,
            alternating_stretch=args.alternating_stretch,
            boundary_stretch=args.boundary_stretch,
            word_stretch=args.word_stretch,
            stretch_factor=args.stretch_factor,
            repeat_weight=args.repeat_weight,
            repeat_count=args.repeat_count,
            repeat_style=args.repeat_style,
            stutter=args.stutter,
            stutter_count=args.stutter_count,
```

**Step 4: Run tests to verify they pass**

Run: `cd glottisdale && python -m pytest tests/test_cli.py -v`
Expected: PASS. The `test_cli_passes_stretch_repeat_to_process` test will fail until Task 6 adds the params to `process()` — that's OK, the other CLI-only tests should pass now. Alternatively, mock `process` to accept any kwargs.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/cli.py glottisdale/tests/test_cli.py
git commit -m "feat(glottisdale): add CLI flags for stretch, repeat, stutter"
```

---

### Task 6: Integrate transforms into the pipeline

This is the largest task. It wires stutter, syllable stretch, word stretch, word repeat, and global speed into `__init__.py:process()`.

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py`
- Test: `glottisdale/tests/test_pipeline.py`

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_pipeline.py`:

```python
@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_accepts_stretch_params(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """process() should accept all stretch/repeat parameters without TypeError."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
        # Stretch params
        random_stretch=0.3,
        stretch_factor="1.5-3.0",
        # Repeat params
        repeat_weight=0.2,
        repeat_count="1-2",
        repeat_style="exact",
        # Stutter params
        stutter=0.3,
        stutter_count="1-2",
    )
    assert result.concatenated.exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_stutter_increases_syllable_count(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """Stutter should cause concatenate_clips to receive more syllable paths per word."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    # 4 syllables so we get at least one multi-syllable word
    syllables = [
        Syllable([Phoneme("AH0", i * 0.2, (i + 1) * 0.2)],
                 i * 0.2, (i + 1) * 0.2, f"word{i}", i)
        for i in range(4)
    ]

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "test",
        "words": [],
        "syllables": syllables,
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    concat_call_args = []

    def fake_concat(clips, output_path, **kwargs):
        concat_call_args.append((len(clips), output_path))
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    # With 100% stutter, every syllable gets duplicated
    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        syllables_per_clip="4",
        seed=42,
        stutter=1.0,
        stutter_count="1",
    )

    # Find word-level concat calls (they write to clips_dir)
    word_concats = [
        (n, p) for n, p in concat_call_args
        if "word" in str(p)
    ]
    # Each word concat should have 2x the syllables (original + 1 stutter copy each)
    if word_concats:
        for n, p in word_concats:
            assert n >= 2  # at least some duplication happened


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_all_stretch_repeat_disabled(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """With all stretch/repeat features at None/default, behavior is unchanged."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello",
        "words": [],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
        # All defaults — no stretch or repeat
    )
    assert result.concatenated.exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd glottisdale && python -m pytest tests/test_pipeline.py::test_process_accepts_stretch_params -v`
Expected: FAIL — `TypeError: process() got an unexpected keyword argument 'random_stretch'`

**Step 3: Write the implementation**

Modify `glottisdale/src/glottisdale/__init__.py`:

1. Add new params to `process()` signature (after the audio polish params, line 218):

```python
    # Stretch params (all off by default)
    speed: float | None = None,
    random_stretch: float | None = None,
    alternating_stretch: int | None = None,
    boundary_stretch: int | None = None,
    word_stretch: float | None = None,
    stretch_factor: str = "2.0",
    # Repeat params (all off by default)
    repeat_weight: float | None = None,
    repeat_count: str = "1-2",
    repeat_style: str = "exact",
    # Stutter params (all off by default)
    stutter: float | None = None,
    stutter_count: str = "1-2",
```

2. Add imports at top:

```python
from glottisdale.stretch import (
    StretchConfig,
    parse_stretch_factor,
    parse_count_range,
    resolve_stretch_factor,
    should_stretch_syllable,
    apply_stutter,
    apply_word_repeat,
)
from glottisdale.audio import time_stretch_clip
```

3. Parse config early in `process()` (after existing `_parse_range` calls):

```python
    stretch_config = StretchConfig(
        random_stretch=random_stretch,
        alternating_stretch=alternating_stretch,
        boundary_stretch=boundary_stretch,
        word_stretch=word_stretch,
        stretch_factor=parse_stretch_factor(stretch_factor),
    )
    has_syllable_stretch = any([
        random_stretch is not None,
        alternating_stretch is not None,
        boundary_stretch is not None,
    ])
    stutter_count_range = parse_count_range(stutter_count) if stutter else None
    repeat_count_range = parse_count_range(repeat_count) if repeat_weight else None
```

4. After volume normalization (line 446) and before word assembly (line 448), insert **Step 8a: Stutter** and **Step 8b: Syllable stretch**:

```python
        # === Step 8a: Stutter — duplicate syllable clips within words ===
        if stutter is not None:
            for word_idx, word_syls in enumerate(words):
                word_syl_paths = [
                    info[2] for info in all_syl_clip_info
                    if info[0] == word_idx and info[2].exists()
                ]
                stuttered = apply_stutter(
                    word_syl_paths, stutter, stutter_count_range, rng
                )
                # Replace the entries in all_syl_clip_info for this word
                # Remove old entries for this word
                all_syl_clip_info = [
                    info for info in all_syl_clip_info
                    if info[0] != word_idx
                ]
                # Add stuttered entries
                for syl_idx, path in enumerate(stuttered):
                    # Find original syllable for metadata (use first matching)
                    syl = word_syls[min(syl_idx, len(word_syls) - 1)]
                    all_syl_clip_info.append((word_idx, syl_idx, path, syl))

        # === Step 8b: Syllable stretch — stretch individual syllable clips ===
        if has_syllable_stretch:
            try:
                global_syl_idx = 0
                for word_idx, word_syls in enumerate(words):
                    word_entries = sorted(
                        [info for info in all_syl_clip_info if info[0] == word_idx],
                        key=lambda x: x[1],
                    )
                    word_syl_count = len(word_entries)
                    for entry in word_entries:
                        _, syl_idx, clip_path, syl = entry
                        if clip_path.exists() and get_duration(clip_path) >= 0.08:
                            if should_stretch_syllable(
                                global_syl_idx, syl_idx, word_syl_count,
                                rng, stretch_config,
                            ):
                                factor = resolve_stretch_factor(
                                    stretch_config.stretch_factor, rng
                                )
                                stretched = tmpdir / f"stretched_{clip_path.name}"
                                time_stretch_clip(clip_path, stretched, factor)
                                shutil.move(stretched, clip_path)
                        global_syl_idx += 1
            except Exception:
                logger.debug("Syllable stretch failed, skipping")
```

5. After word assembly (line 481) and before phrase grouping (line 486), insert **Step 10a: Word stretch** and **Step 11: Word repeat**:

```python
        # === Step 10a: Word stretch — stretch assembled word WAVs ===
        if word_stretch is not None:
            try:
                for clip in clips:
                    if clip.output_path.exists() and rng.random() < word_stretch:
                        dur = get_duration(clip.output_path)
                        if dur >= 0.08:
                            factor = resolve_stretch_factor(
                                stretch_config.stretch_factor, rng
                            )
                            stretched = tmpdir / f"wstretched_{clip.output_path.name}"
                            time_stretch_clip(clip.output_path, stretched, factor)
                            shutil.move(stretched, clip.output_path)
            except Exception:
                logger.debug("Word stretch failed, skipping")

        # === Step 11: Word repeat — duplicate words in clip list ===
        if repeat_weight is not None:
            try:
                clips = apply_word_repeat(
                    clips, repeat_weight, repeat_count_range,
                    repeat_style, rng,
                )
                valid_word_paths = [c.output_path for c in clips
                                    if c.output_path.exists()]
            except Exception:
                logger.debug("Word repeat failed, skipping")
```

Note: this also requires updating the `valid_word_paths` line (currently line 484) to come after the repeat step instead.

6. After final concatenation (line 619) and before pink noise mixing (line 621), insert **Step 16: Global speed**:

```python
        # === Step 16: Global speed — stretch entire output ===
        if speed is not None and concatenated_path.exists():
            try:
                # speed 0.5 = half speed = stretch factor 2.0
                speed_factor = 1.0 / speed
                sped = tmpdir / "speed_output.wav"
                time_stretch_clip(concatenated_path, sped, speed_factor)
                shutil.move(sped, concatenated_path)
            except Exception:
                logger.debug("Global speed failed, skipping")
```

**Step 4: Run tests to verify they pass**

Run: `cd glottisdale && python -m pytest tests/test_pipeline.py -v`
Expected: PASS (all existing + new tests)

Also run all tests to check for regressions:
Run: `cd glottisdale && python -m pytest tests/ -v`
Expected: PASS (all 112+ tests)

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): integrate stretch, repeat, stutter into pipeline"
```

---

### Task 7: Update GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/glottisdale.yml:43`

**Step 1: Add librubberband-dev to system dependencies**

Change the Install system dependencies line:

```yaml
      - name: Install system dependencies
        run: sudo apt-get update && sudo apt-get install -y ffmpeg espeak-ng librubberband-dev
```

**Step 2: Commit**

```bash
git add .github/workflows/glottisdale.yml
git commit -m "ci(glottisdale): add librubberband-dev for time stretch"
```

---

### Task 8: Run full test suite and fix any issues

**Step 1: Run all tests**

Run: `cd glottisdale && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: If any failures, debug and fix**

Iterate until all tests pass. Common issues to watch for:
- Import ordering — make sure `time_stretch_clip` is imported in `__init__.py`
- `all_syl_clip_info` mutation during stutter — the list replacement logic needs care
- `valid_word_paths` used after repeat — must be rebuilt from the updated `clips` list
- Mock patching — new imports in `__init__.py` may need patching in tests

**Step 3: Final commit if fixes needed**

```bash
git add -A
git commit -m "fix(glottisdale): fix test failures in stretch/repeat integration"
```

---

### Task 9: Update MEMORY.md and design docs

**Files:**
- Modify: `/Users/jake/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md`

**Step 1: Add stretch/repeat section to MEMORY.md**

Add under the Glottisdale section:

```markdown
### Time Stretch & Word Repeat
- `stretch.py` — stretch selection logic: StretchConfig, should_stretch_syllable(), apply_stutter(), apply_word_repeat()
- 5 stretch modes: `--speed` (global), `--random-stretch`, `--alternating-stretch`, `--boundary-stretch`, `--word-stretch`
- `--stretch-factor` uses "single or range" syntax like existing CLI flags
- Stutter at step 8a (before word assembly), syllable stretch at 8b, word stretch at 10a, word repeat at 11, global speed at 16
- All off by default, pitch-preserving via ffmpeg rubberband filter
- rubberband graceful fallback: logs warning and copies file if filter unavailable
- librubberband-dev added to CI workflow
```

**Step 2: Commit**

```bash
git add /Users/jake/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md
git commit -m "docs: update memory with stretch/repeat conventions"
```

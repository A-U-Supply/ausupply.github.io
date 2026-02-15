# Glottisdale Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a syllable-level audio collage tool that segments speech into syllables and randomly reassembles them.

**Architecture:** Whisper ASR for word-level timestamps → g2p_en for ARPABET phoneme conversion → vendored syllabifier for syllable groupings → distribute word timing proportionally across syllables → ffmpeg for audio cutting and concatenation. Library-first design with optional Slack integration.

**Tech Stack:** Python 3.10+, openai-whisper, g2p_en, ffmpeg (system), pytest. Optional: slack-sdk for Slack integration.

**Design change from original spec:** ForceAlign was dropped after discovering its phoneme timestamps are fake (just word duration / phoneme count). The pipeline uses Whisper word timestamps + g2p_en + syllabify instead, which produces identical results with fewer dependencies. The abstract aligner interface is retained for future BFA integration (which does real phoneme-level alignment).

**Design doc:** `docs/plans/2026-02-15-glottisdale-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `glottisdale/pyproject.toml`
- Create: `glottisdale/src/glottisdale/__init__.py`
- Create: `glottisdale/src/glottisdale/types.py`
- Create: `glottisdale/tests/__init__.py`
- Create: `glottisdale/tests/test_types.py`

**Step 1: Create directory structure**

```bash
mkdir -p glottisdale/src/glottisdale glottisdale/tests glottisdale/slack/glottisdale_slack
```

**Step 2: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "glottisdale"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "openai-whisper",
    "g2p_en",
]

[project.optional-dependencies]
slack = ["slack-sdk>=3.27.0", "requests>=2.31.0"]
dev = ["pytest>=8.0.0"]

[project.scripts]
glottisdale = "glottisdale.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 3: Write types.py with dataclasses**

```python
"""Core data types for glottisdale."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Phoneme:
    """A single phoneme with timing."""
    label: str       # ARPABET e.g. "AH0", or IPA if BFA
    start: float     # seconds
    end: float       # seconds


@dataclass
class Syllable:
    """A group of phonemes forming one syllable."""
    phonemes: list[Phoneme]
    start: float        # first phoneme start (seconds)
    end: float          # last phoneme end (seconds)
    word: str           # parent word
    word_index: int     # position in transcript


@dataclass
class Clip:
    """An audio clip containing one or more syllables."""
    syllables: list[Syllable]
    start: float        # with padding applied (seconds)
    end: float          # with padding applied (seconds)
    source: str         # input filename
    output_path: Path = field(default_factory=lambda: Path())


@dataclass
class Result:
    """Output of the glottisdale pipeline."""
    clips: list[Clip]
    concatenated: Path
    transcript: str
    manifest: dict
```

**Step 4: Write test_types.py**

```python
"""Tests for core data types."""

from pathlib import Path
from glottisdale.types import Phoneme, Syllable, Clip, Result


def test_phoneme_creation():
    p = Phoneme(label="AH0", start=0.1, end=0.2)
    assert p.label == "AH0"
    assert p.start == 0.1
    assert p.end == 0.2


def test_syllable_creation():
    p1 = Phoneme("HH", 0.1, 0.15)
    p2 = Phoneme("AH0", 0.15, 0.25)
    syl = Syllable(phonemes=[p1, p2], start=0.1, end=0.25, word="hello", word_index=0)
    assert len(syl.phonemes) == 2
    assert syl.word == "hello"


def test_clip_creation():
    p = Phoneme("AH0", 0.1, 0.2)
    syl = Syllable([p], 0.1, 0.2, "a", 0)
    clip = Clip(syllables=[syl], start=0.075, end=0.225, source="test.wav")
    assert clip.source == "test.wav"
    assert clip.start == 0.075


def test_result_creation():
    result = Result(clips=[], concatenated=Path("out.ogg"), transcript="hello", manifest={})
    assert result.transcript == "hello"
    assert result.concatenated == Path("out.ogg")
```

**Step 5: Write empty __init__.py**

```python
"""Glottisdale — syllable-level audio collage tool."""
```

Also create `glottisdale/tests/__init__.py` as empty file.

**Step 6: Run tests**

```bash
cd glottisdale && pip install -e ".[dev]" && pytest tests/test_types.py -v
```

Expected: All 4 tests PASS.

**Step 7: Commit**

```bash
git add glottisdale/
git commit -m "feat(glottisdale): project scaffolding and core data types"
```

---

### Task 2: Vendor Syllabifier and Write Wrapper

**Files:**
- Create: `glottisdale/src/glottisdale/syllabify_arpabet.py` (vendored)
- Create: `glottisdale/src/glottisdale/syllabify.py`
- Create: `glottisdale/tests/test_syllabify.py`

**Step 1: Vendor kylebgorman/syllabify**

Download `syllabify.py` from https://github.com/kylebgorman/syllabify and save as `glottisdale/src/glottisdale/syllabify_arpabet.py`. Add a header comment:

```python
# Vendored from https://github.com/kylebgorman/syllabify (MIT License)
# ARPABET syllabifier using Maximum Onset Principle
```

This file exposes `syllabify(pron)` which takes a list of ARPABET strings and returns a list of `(onset, nucleus, coda)` tuples.

**Step 2: Write the failing test for the syllabify wrapper**

`glottisdale/tests/test_syllabify.py`:

```python
"""Tests for syllabification wrapper."""

from glottisdale.types import Phoneme, Syllable
from glottisdale.syllabify import syllabify_word, syllabify_words


def test_syllabify_word_single_syllable():
    """'cat' = K AE1 T → 1 syllable."""
    phonemes = ["K", "AE1", "T"]
    word_start = 0.0
    word_end = 0.3
    syllables = syllabify_word(phonemes, word_start, word_end, "cat", word_index=0)
    assert len(syllables) == 1
    assert syllables[0].word == "cat"
    assert syllables[0].start == 0.0
    assert syllables[0].end == 0.3
    assert len(syllables[0].phonemes) == 3


def test_syllabify_word_two_syllables():
    """'camel' = K AE1 M AH0 L → 2 syllables."""
    phonemes = ["K", "AE1", "M", "AH0", "L"]
    syllables = syllabify_word(phonemes, 0.0, 0.5, "camel", word_index=1)
    assert len(syllables) == 2
    # First syllable gets proportional time: 2 phonemes / 5 total * 0.5s = 0.2s
    # Second syllable: 3 phonemes / 5 total * 0.5s = 0.3s
    assert syllables[0].start == 0.0
    assert abs(syllables[0].end - 0.2) < 0.001
    assert abs(syllables[1].start - 0.2) < 0.001
    assert syllables[1].end == 0.5


def test_syllabify_word_three_syllables():
    """'banana' = B AH0 N AE1 N AH0 → 3 syllables."""
    phonemes = ["B", "AH0", "N", "AE1", "N", "AH0"]
    syllables = syllabify_word(phonemes, 0.0, 0.6, "banana", word_index=0)
    assert len(syllables) == 3


def test_syllabify_words():
    """Process multiple words into a flat syllable list."""
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]
    syllables = syllabify_words(words)
    # "hello" = HH AH0 L OW1 → 2 syllables
    # "world" = W ER1 L D → 1 syllable
    assert len(syllables) == 3
    assert syllables[0].word == "hello"
    assert syllables[0].word_index == 0
    assert syllables[2].word == "world"
    assert syllables[2].word_index == 1


def test_syllabify_word_unknown_word():
    """Unknown word (not in g2p) should still produce at least 1 syllable."""
    syllables = syllabify_word(
        ["AH0"], 0.0, 0.1, "xyzzy", word_index=0
    )
    assert len(syllables) >= 1
```

**Step 3: Run test to verify it fails**

```bash
cd glottisdale && pytest tests/test_syllabify.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'glottisdale.syllabify'`

**Step 4: Write syllabify.py**

```python
"""Syllabification: words with timestamps → syllable boundaries."""

from pathlib import Path
from g2p_en import G2p
from glottisdale.types import Phoneme, Syllable

# Import vendored ARPABET syllabifier
from glottisdale.syllabify_arpabet import syllabify as _arpabet_syllabify

_g2p = None


def _get_g2p() -> G2p:
    """Lazy-init g2p_en (downloads model on first use)."""
    global _g2p
    if _g2p is None:
        _g2p = G2p()
    return _g2p


def syllabify_word(
    phonemes: list[str],
    word_start: float,
    word_end: float,
    word: str,
    word_index: int,
) -> list[Syllable]:
    """Split a word's phonemes into syllables with estimated timestamps.

    Timestamps are distributed proportionally across syllables based on
    phoneme count per syllable.
    """
    if not phonemes:
        return []

    try:
        syl_tuples = _arpabet_syllabify(phonemes)
    except (ValueError, KeyError):
        # Fallback: treat entire word as one syllable
        syl_tuples = [([], phonemes, [])]

    if not syl_tuples:
        syl_tuples = [([], phonemes, [])]

    # Count phonemes per syllable for proportional timing
    syl_phoneme_lists = [onset + nucleus + coda for onset, nucleus, coda in syl_tuples]
    total_phonemes = sum(len(s) for s in syl_phoneme_lists)
    if total_phonemes == 0:
        total_phonemes = 1

    word_duration = word_end - word_start
    syllables = []
    current_time = word_start

    for syl_phones in syl_phoneme_lists:
        proportion = len(syl_phones) / total_phonemes
        syl_duration = word_duration * proportion
        syl_end = current_time + syl_duration

        # Create Phoneme objects with evenly distributed times within syllable
        phoneme_objects = []
        if syl_phones:
            ph_dur = syl_duration / len(syl_phones)
            ph_time = current_time
            for label in syl_phones:
                phoneme_objects.append(Phoneme(
                    label=label,
                    start=round(ph_time, 4),
                    end=round(ph_time + ph_dur, 4),
                ))
                ph_time += ph_dur

        syllables.append(Syllable(
            phonemes=phoneme_objects,
            start=round(current_time, 4),
            end=round(syl_end, 4),
            word=word,
            word_index=word_index,
        ))
        current_time = syl_end

    return syllables


def syllabify_words(
    words: list[dict],
) -> list[Syllable]:
    """Convert word-level timestamps to syllable-level timestamps.

    Args:
        words: List of dicts with 'word', 'start', 'end' keys
               (as returned by Whisper with word_timestamps=True).

    Returns:
        Flat list of Syllable objects across all words.
    """
    g2p = _get_g2p()
    all_syllables = []

    for i, w in enumerate(words):
        text = w["word"].strip()
        if not text:
            continue

        # g2p_en returns list of phonemes + spaces between words
        raw_phonemes = g2p(text)
        phonemes = [p for p in raw_phonemes if p.strip() and p != " "]

        if not phonemes:
            continue

        syls = syllabify_word(
            phonemes=phonemes,
            word_start=w["start"],
            word_end=w["end"],
            word=text,
            word_index=i,
        )
        all_syllables.extend(syls)

    return all_syllables
```

**Step 5: Run tests**

```bash
cd glottisdale && pytest tests/test_syllabify.py -v
```

Expected: All 5 tests PASS. If any phoneme counts are off (g2p_en may produce slightly different phoneme sequences), adjust test assertions to match actual g2p_en output.

**Step 6: Commit**

```bash
git add glottisdale/src/glottisdale/syllabify_arpabet.py glottisdale/src/glottisdale/syllabify.py glottisdale/tests/test_syllabify.py
git commit -m "feat(glottisdale): syllabification with ARPABET and proportional timing"
```

---

### Task 3: Audio Processing — Detection and Extraction

**Files:**
- Create: `glottisdale/src/glottisdale/audio.py`
- Create: `glottisdale/tests/test_audio.py`
- Create: `glottisdale/tests/fixtures/` (test audio files)

**Step 1: Generate a test audio fixture**

```bash
mkdir -p glottisdale/tests/fixtures
# Generate a 2-second sine wave test WAV
ffmpeg -y -f lavfi -i "sine=frequency=440:duration=2" -ar 16000 -ac 1 glottisdale/tests/fixtures/test_tone.wav
# Generate a 1-second silent WAV
ffmpeg -y -f lavfi -i "anullsrc=r=16000:cl=mono" -t 1 glottisdale/tests/fixtures/test_silence.wav
```

**Step 2: Write failing tests for audio detection and extraction**

`glottisdale/tests/test_audio.py`:

```python
"""Tests for audio processing (ffmpeg wrappers)."""

import subprocess
from pathlib import Path
import pytest

from glottisdale.audio import (
    detect_input_type,
    extract_audio,
    get_duration,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_audio_file():
    result = detect_input_type(FIXTURES / "test_tone.wav")
    assert result == "audio"


def test_detect_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        detect_input_type(Path("/nonexistent/file.wav"))


def test_extract_audio_from_audio(tmp_path):
    """Extracting audio from an audio file just resamples."""
    out = tmp_path / "extracted.wav"
    extract_audio(FIXTURES / "test_tone.wav", out)
    assert out.exists()
    assert out.stat().st_size > 0
    duration = get_duration(out)
    assert abs(duration - 2.0) < 0.1


def test_get_duration():
    duration = get_duration(FIXTURES / "test_tone.wav")
    assert abs(duration - 2.0) < 0.1
```

**Step 3: Run tests to verify they fail**

```bash
cd glottisdale && pytest tests/test_audio.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 4: Write audio.py — detection, extraction, duration**

```python
"""Audio processing via ffmpeg/ffprobe."""

import json
import subprocess
from pathlib import Path


def _run_ffprobe(path: Path, *args: str) -> str:
    """Run ffprobe and return stdout."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        *args, str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    result.check_returncode()
    return result.stdout


def detect_input_type(path: Path) -> str:
    """Return 'video' or 'audio' based on stream types."""
    output = _run_ffprobe(path, "-show_streams")
    data = json.loads(output)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            return "video"
    return "audio"


def get_duration(path: Path) -> float:
    """Get file duration in seconds."""
    output = _run_ffprobe(path, "-show_format")
    data = json.loads(output)
    return float(data["format"]["duration"])


def extract_audio(input_path: Path, output_path: Path) -> Path:
    """Extract/resample audio to 16kHz mono WAV for Whisper."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vn", "-ar", "16000", "-ac", "1", "-f", "wav",
        str(output_path),
    ]
    subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
    ).check_returncode()
    return output_path
```

**Step 5: Run tests**

```bash
cd glottisdale && pytest tests/test_audio.py -v
```

Expected: All 4 tests PASS.

**Step 6: Commit**

```bash
git add glottisdale/src/glottisdale/audio.py glottisdale/tests/test_audio.py glottisdale/tests/fixtures/
git commit -m "feat(glottisdale): audio detection, extraction, and duration via ffmpeg"
```

---

### Task 4: Audio Processing — Cutting and Concatenation

**Files:**
- Modify: `glottisdale/src/glottisdale/audio.py`
- Modify: `glottisdale/tests/test_audio.py`

**Step 1: Write failing tests for cutting and concatenation**

Append to `glottisdale/tests/test_audio.py`:

```python
from glottisdale.audio import cut_clip, generate_silence, concatenate_clips


def test_cut_clip(tmp_path):
    """Cut a 0.5s clip from a 2s source."""
    out = tmp_path / "clip.ogg"
    cut_clip(
        input_path=FIXTURES / "test_tone.wav",
        output_path=out,
        start=0.5,
        end=1.0,
        padding_ms=0,
        fade_ms=10,
    )
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 0.5) < 0.05


def test_cut_clip_with_padding(tmp_path):
    """Padding extends the clip by padding_ms on each side."""
    out = tmp_path / "clip.ogg"
    cut_clip(
        input_path=FIXTURES / "test_tone.wav",
        output_path=out,
        start=0.5,
        end=1.0,
        padding_ms=25,
        fade_ms=10,
    )
    assert out.exists()
    duration = get_duration(out)
    # 0.5s + 2*0.025s padding = 0.55s
    assert abs(duration - 0.55) < 0.05


def test_cut_clip_padding_clamped(tmp_path):
    """Padding at file boundaries is clamped."""
    out = tmp_path / "clip.ogg"
    cut_clip(
        input_path=FIXTURES / "test_tone.wav",
        output_path=out,
        start=0.0,
        end=0.1,
        padding_ms=100,  # Would go negative without clamping
        fade_ms=10,
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_silence(tmp_path):
    """Generate a silent OGG of specified duration."""
    out = tmp_path / "silence.ogg"
    generate_silence(out, duration_ms=100, sample_rate=16000)
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 0.1) < 0.05


def test_concatenate_clips_no_gaps(tmp_path):
    """Concatenate two clips without gaps."""
    # Cut two clips from test tone
    clip1 = tmp_path / "c1.ogg"
    clip2 = tmp_path / "c2.ogg"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 0.5, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.5, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "concat.ogg"
    concatenate_clips([clip1, clip2], out, crossfade_ms=0)
    assert out.exists()
    duration = get_duration(out)
    assert abs(duration - 1.0) < 0.1


def test_concatenate_with_gaps(tmp_path):
    """Concatenate with silence gaps."""
    clip1 = tmp_path / "c1.ogg"
    clip2 = tmp_path / "c2.ogg"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 0.3, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.5, 0.8, padding_ms=0, fade_ms=0)

    out = tmp_path / "concat.ogg"
    concatenate_clips([clip1, clip2], out, crossfade_ms=0, gap_durations_ms=[200])
    assert out.exists()
    duration = get_duration(out)
    # 0.3 + 0.2 gap + 0.3 = 0.8s
    assert abs(duration - 0.8) < 0.1
```

**Step 2: Run tests to verify they fail**

```bash
cd glottisdale && pytest tests/test_audio.py::test_cut_clip -v
```

Expected: FAIL with `ImportError: cannot import name 'cut_clip'`

**Step 3: Implement cut_clip, generate_silence, concatenate_clips**

Add to `glottisdale/src/glottisdale/audio.py`:

```python
def cut_clip(
    input_path: Path,
    output_path: Path,
    start: float,
    end: float,
    padding_ms: float = 25,
    fade_ms: float = 10,
) -> Path:
    """Cut an audio clip with padding and fade."""
    file_duration = get_duration(input_path)
    padding_s = padding_ms / 1000.0
    fade_s = fade_ms / 1000.0

    # Apply padding, clamp to file bounds
    actual_start = max(0.0, start - padding_s)
    actual_end = min(file_duration, end + padding_s)
    duration = actual_end - actual_start

    if duration <= 0:
        raise ValueError(f"Invalid clip duration: {duration}s")

    # Build audio filter for fades
    filters = []
    if fade_s > 0 and duration > fade_s * 2:
        fade_out_start = duration - fade_s
        filters.append(f"afade=t=in:d={fade_s}:curve=hsin")
        filters.append(f"afade=t=out:st={fade_out_start}:d={fade_s}:curve=hsin")

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{actual_start:.4f}",
        "-i", str(input_path),
        "-t", f"{duration:.4f}",
    ]
    if filters:
        cmd.extend(["-af", ",".join(filters)])
    cmd.extend(["-c:a", "libvorbis", "-q:a", "4", str(output_path)])

    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path


def generate_silence(output_path: Path, duration_ms: float, sample_rate: int = 16000) -> Path:
    """Generate a silent OGG file."""
    duration_s = duration_ms / 1000.0
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", f"{duration_s:.4f}",
        "-c:a", "libvorbis", "-q:a", "4",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path


def concatenate_clips(
    clip_paths: list[Path],
    output_path: Path,
    crossfade_ms: float = 0,
    gap_durations_ms: list[float] | None = None,
) -> Path:
    """Concatenate audio clips with optional gaps and crossfade.

    Args:
        clip_paths: Ordered list of OGG clip files.
        output_path: Where to write the concatenated result.
        crossfade_ms: Crossfade duration between clips (0 = hard cut).
        gap_durations_ms: Silence duration between each pair of clips.
            Length must be len(clip_paths) - 1. If None, no gaps.
    """
    import tempfile

    if not clip_paths:
        raise ValueError("No clips to concatenate")

    if len(clip_paths) == 1:
        # Just copy
        import shutil
        shutil.copy2(clip_paths[0], output_path)
        return output_path

    # Build list of files to concat (interleaved with silence if gaps)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        concat_list = []

        for i, clip in enumerate(clip_paths):
            concat_list.append(clip)
            if gap_durations_ms and i < len(clip_paths) - 1:
                gap_ms = gap_durations_ms[i] if i < len(gap_durations_ms) else 0
                if gap_ms > 0:
                    silence_path = tmpdir / f"silence_{i:04d}.ogg"
                    generate_silence(silence_path, gap_ms)
                    concat_list.append(silence_path)

        if crossfade_ms > 0:
            _concatenate_with_crossfade(concat_list, output_path, crossfade_ms)
        else:
            _concatenate_simple(concat_list, output_path)

    return output_path


def _concatenate_simple(clip_paths: list[Path], output_path: Path) -> None:
    """Concatenate via ffmpeg concat demuxer (no crossfade)."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip in clip_paths:
            f.write(f"file '{clip}'\n")
        list_path = f.name

    try:
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_path, "-c", "copy", str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120).check_returncode()
    finally:
        Path(list_path).unlink(missing_ok=True)


def _concatenate_with_crossfade(
    clip_paths: list[Path], output_path: Path, crossfade_ms: float
) -> None:
    """Concatenate with acrossfade filters between clips."""
    crossfade_s = crossfade_ms / 1000.0
    n = len(clip_paths)

    if n <= 1:
        import shutil
        shutil.copy2(clip_paths[0], output_path)
        return

    # Build filter_complex chain
    inputs = []
    for i, clip in enumerate(clip_paths):
        inputs.extend(["-i", str(clip)])

    filter_parts = []
    current_label = "[0]"

    for i in range(1, n):
        next_label = f"[{i}]"
        out_label = f"[a{i}]" if i < n - 1 else "[out]"
        filter_parts.append(
            f"{current_label}{next_label}acrossfade=d={crossfade_s}:c1=tri:c2=tri{out_label}"
        )
        current_label = out_label

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-c:a", "libvorbis", "-q:a", "4",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120).check_returncode()
```

**Step 5: Run tests**

```bash
cd glottisdale && pytest tests/test_audio.py -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add glottisdale/src/glottisdale/audio.py glottisdale/tests/test_audio.py
git commit -m "feat(glottisdale): audio cutting, silence generation, and concatenation"
```

---

### Task 5: Transcription (Whisper Wrapper)

**Files:**
- Create: `glottisdale/src/glottisdale/transcribe.py`
- Create: `glottisdale/tests/test_transcribe.py`

**Step 1: Write the test**

The transcribe module wraps Whisper. Unit tests mock the model to avoid downloading ~140MB.

```python
"""Tests for Whisper transcription wrapper."""

from unittest.mock import MagicMock, patch
from pathlib import Path

from glottisdale.transcribe import transcribe


def _mock_whisper_result():
    """A realistic Whisper result with word timestamps."""
    return {
        "text": " Hello world.",
        "language": "en",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "text": " Hello world.",
                "words": [
                    {"word": " Hello", "start": 0.0, "end": 0.8, "probability": 0.95},
                    {"word": " world", "start": 0.9, "end": 1.5, "probability": 0.92},
                ],
            }
        ],
    }


@patch("glottisdale.transcribe.whisper")
def test_transcribe_returns_words(mock_whisper):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_whisper_result()
    mock_whisper.load_model.return_value = mock_model

    result = transcribe(Path("fake.wav"), model_name="base")

    assert result["text"] == "Hello world."
    assert len(result["words"]) == 2
    assert result["words"][0]["word"] == "Hello"
    assert result["words"][0]["start"] == 0.0
    assert result["words"][0]["end"] == 0.8
    assert result["words"][1]["word"] == "world"


@patch("glottisdale.transcribe.whisper")
def test_transcribe_strips_word_whitespace(mock_whisper):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_whisper_result()
    mock_whisper.load_model.return_value = mock_model

    result = transcribe(Path("fake.wav"))

    # Words should have leading whitespace stripped
    for w in result["words"]:
        assert w["word"] == w["word"].strip()
```

**Step 2: Run to verify failure**

```bash
cd glottisdale && pytest tests/test_transcribe.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement transcribe.py**

```python
"""Whisper ASR transcription with word-level timestamps."""

from pathlib import Path

import whisper

_model_cache: dict[str, object] = {}


def transcribe(
    audio_path: Path,
    model_name: str = "base",
    language: str = "en",
) -> dict:
    """Transcribe audio and return word-level timestamps.

    Returns:
        Dict with keys:
            text: Full transcript (stripped)
            words: List of dicts with 'word', 'start', 'end' keys
            language: Detected or specified language
    """
    if model_name not in _model_cache:
        _model_cache[model_name] = whisper.load_model(model_name)
    model = _model_cache[model_name]

    result = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language=language,
    )

    # Flatten words across segments, strip whitespace
    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
            })

    return {
        "text": result["text"].strip(),
        "words": words,
        "language": result.get("language", language),
    }
```

**Step 4: Run tests**

```bash
cd glottisdale && pytest tests/test_transcribe.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/transcribe.py glottisdale/tests/test_transcribe.py
git commit -m "feat(glottisdale): Whisper transcription wrapper with word timestamps"
```

---

### Task 6: Aligner Interface

**Files:**
- Create: `glottisdale/src/glottisdale/align.py`
- Create: `glottisdale/tests/test_align.py`

The aligner interface provides an abstraction point. The default backend uses Whisper word timestamps + g2p_en + syllabify (already implemented). Future BFA backend would replace the phoneme-level estimation with real forced alignment.

**Step 1: Write the test**

```python
"""Tests for aligner interface."""

from pathlib import Path
from unittest.mock import patch

from glottisdale.align import get_aligner, DefaultAligner
from glottisdale.types import Syllable


def test_get_aligner_default():
    aligner = get_aligner("default")
    assert isinstance(aligner, DefaultAligner)


def test_get_aligner_unknown():
    import pytest
    with pytest.raises(ValueError, match="Unknown aligner"):
        get_aligner("nonexistent")


@patch("glottisdale.align.transcribe")
def test_default_aligner_produces_syllables(mock_transcribe):
    mock_transcribe.return_value = {
        "text": "Hello world",
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
        "language": "en",
    }

    aligner = DefaultAligner(whisper_model="base")
    result = aligner.process(Path("fake.wav"))

    assert result["text"] == "Hello world"
    assert len(result["syllables"]) >= 2  # "hello" has 2 syllables
    assert all(isinstance(s, Syllable) for s in result["syllables"])
    # Check hello's syllables
    hello_syls = [s for s in result["syllables"] if s.word == "Hello"]
    assert len(hello_syls) == 2
```

**Step 2: Run to verify failure**

```bash
cd glottisdale && pytest tests/test_align.py -v
```

**Step 3: Implement align.py**

```python
"""Aligner interface and backends."""

from abc import ABC, abstractmethod
from pathlib import Path

from glottisdale.types import Syllable
from glottisdale.transcribe import transcribe
from glottisdale.syllabify import syllabify_words


class Aligner(ABC):
    """Abstract base for speech alignment backends."""

    @abstractmethod
    def process(self, audio_path: Path) -> dict:
        """Transcribe and align audio, returning syllable-level timestamps.

        Returns:
            Dict with keys:
                text: Full transcript
                words: List of word dicts with timestamps
                syllables: List of Syllable objects
        """


class DefaultAligner(Aligner):
    """Whisper ASR + g2p_en + ARPABET syllabifier.

    Word-level timestamps from Whisper, phoneme conversion via g2p_en,
    syllable timing estimated by proportional distribution.
    """

    def __init__(self, whisper_model: str = "base", language: str = "en"):
        self.whisper_model = whisper_model
        self.language = language

    def process(self, audio_path: Path) -> dict:
        result = transcribe(audio_path, model_name=self.whisper_model, language=self.language)
        syllables = syllabify_words(result["words"])
        return {
            "text": result["text"],
            "words": result["words"],
            "syllables": syllables,
        }


# Registry of available backends
_ALIGNERS = {
    "default": DefaultAligner,
}


def get_aligner(name: str, **kwargs) -> Aligner:
    """Get an aligner backend by name."""
    if name not in _ALIGNERS:
        raise ValueError(f"Unknown aligner: {name!r}. Available: {list(_ALIGNERS.keys())}")
    return _ALIGNERS[name](**kwargs)
```

**Step 4: Run tests**

```bash
cd glottisdale && pytest tests/test_align.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/align.py glottisdale/tests/test_align.py
git commit -m "feat(glottisdale): aligner interface with default Whisper+g2p backend"
```

---

### Task 7: Pipeline Orchestrator

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py`
- Create: `glottisdale/tests/test_pipeline.py`

This is the `process()` function that ties everything together.

**Step 1: Write the test**

```python
"""Tests for the pipeline orchestrator."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from glottisdale import process
from glottisdale.types import Syllable, Phoneme


def _make_syllables():
    """Fake syllables spanning 0-2 seconds across two words."""
    return [
        Syllable([Phoneme("HH", 0.0, 0.1), Phoneme("AH0", 0.1, 0.25)],
                 0.0, 0.25, "hello", 0),
        Syllable([Phoneme("L", 0.25, 0.35), Phoneme("OW1", 0.35, 0.5)],
                 0.25, 0.5, "hello", 0),
        Syllable([Phoneme("W", 0.6, 0.7), Phoneme("ER1", 0.7, 0.85),
                  Phoneme("L", 0.85, 0.92), Phoneme("D", 0.92, 1.0)],
                 0.6, 1.0, "world", 1),
    ]


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_local_file(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    # Setup mocks
    mock_detect.return_value = "audio"
    mock_extract.return_value = tmp_path / "audio.wav"
    (tmp_path / "audio.wav").touch()

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    # Make cut_clip create empty files
    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    # Make concat create empty file
    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
    )

    assert result.transcript == "hello world"
    assert len(result.clips) == 3
    assert result.concatenated.exists()
    assert (tmp_path / "out" / "manifest.json").exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_respects_target_duration(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    mock_detect.return_value = "audio"
    mock_extract.return_value = tmp_path / "audio.wav"
    (tmp_path / "audio.wav").touch()

    # Create many syllables (10 x 0.2s = 2s total)
    syllables = [
        Syllable([Phoneme("AH0", i * 0.2, (i + 1) * 0.2)],
                 i * 0.2, (i + 1) * 0.2, f"word{i}", i)
        for i in range(10)
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

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=0.5,  # Only ~2-3 syllables worth
        seed=42,
    )

    # Should select fewer syllables to stay near target
    total_duration = sum(c.end - c.start for c in result.clips)
    assert total_duration <= 1.0  # Some slack, but well under 2.0
```

**Step 2: Run to verify failure**

```bash
cd glottisdale && pytest tests/test_pipeline.py -v
```

**Step 3: Implement process() in __init__.py**

```python
"""Glottisdale — syllable-level audio collage tool."""

import json
import random
import shutil
import tempfile
import zipfile
from pathlib import Path

from glottisdale.align import get_aligner
from glottisdale.audio import (
    cut_clip,
    concatenate_clips,
    detect_input_type,
    extract_audio,
    get_duration,
)
from glottisdale.types import Clip, Result, Syllable


def _parse_gap(gap: str) -> tuple[float, float]:
    """Parse gap string like '50-200' or '100' into (min_ms, max_ms)."""
    if "-" in gap:
        parts = gap.split("-", 1)
        return float(parts[0]), float(parts[1])
    val = float(gap)
    return val, val


def _sample_syllables(
    syllables: list[Syllable],
    target_duration: float,
    rng: random.Random,
) -> list[Syllable]:
    """Sample and shuffle syllables to approximately hit target duration."""
    if not syllables:
        return []

    available = list(syllables)
    rng.shuffle(available)

    selected = []
    total = 0.0
    for syl in available:
        syl_dur = syl.end - syl.start
        if total + syl_dur > target_duration and selected:
            break
        selected.append(syl)
        total += syl_dur

    rng.shuffle(selected)
    return selected


def _sample_syllables_multi_source(
    sources: dict[str, list[Syllable]],
    target_duration: float,
    rng: random.Random,
) -> list[Syllable]:
    """Round-robin sample across sources for variety, then shuffle."""
    if not sources:
        return []

    # Round-robin: take one syllable from each source in turn
    source_pools = {}
    for name, syls in sources.items():
        pool = list(syls)
        rng.shuffle(pool)
        source_pools[name] = pool

    selected = []
    total = 0.0
    source_names = list(source_pools.keys())

    while source_names and total < target_duration:
        for name in list(source_names):
            pool = source_pools[name]
            if not pool:
                source_names.remove(name)
                continue
            syl = pool.pop()
            syl_dur = syl.end - syl.start
            selected.append(syl)
            total += syl_dur
            if total >= target_duration:
                break

    rng.shuffle(selected)
    return selected


def process(
    input_paths: list[Path],
    output_dir: str | Path = "./glottisdale-output",
    syllables_per_clip: int = 1,
    target_duration: float = 10.0,
    crossfade_ms: float = 10,
    padding_ms: float = 25,
    gap: str = "50-200",
    aligner: str = "default",
    whisper_model: str = "base",
    seed: int | None = None,
) -> Result:
    """Run the full glottisdale pipeline.

    Args:
        input_paths: Local audio/video files to process.
        output_dir: Directory for output clips and concatenated audio.
        syllables_per_clip: Number of syllables grouped per clip.
        target_duration: Approximate target duration in seconds.
        crossfade_ms: Crossfade between clips in ms (0 = hard cut).
        padding_ms: Padding around each syllable cut in ms.
        gap: Silence between clips, e.g. '50-200' or '0'.
        aligner: Alignment backend name.
        whisper_model: Whisper model size.
        seed: RNG seed for reproducibility.

    Returns:
        Result with clips, concatenated path, transcript, and manifest.
    """
    rng = random.Random(seed)
    output_dir = Path(output_dir)
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    gap_min, gap_max = _parse_gap(gap)
    alignment_engine = get_aligner(aligner, whisper_model=whisper_model)

    # Process each input file
    all_syllables: dict[str, list[Syllable]] = {}
    all_transcripts = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for input_path in input_paths:
            input_path = Path(input_path)
            source_name = input_path.stem

            # Extract audio if needed
            input_type = detect_input_type(input_path)
            if input_type == "video":
                audio_path = tmpdir / f"{source_name}.wav"
                extract_audio(input_path, audio_path)
            else:
                audio_path = tmpdir / f"{source_name}.wav"
                extract_audio(input_path, audio_path)  # Resample to 16kHz

            # Transcribe and syllabify
            result = alignment_engine.process(audio_path)
            all_transcripts.append(f"[{source_name}] {result['text']}")
            all_syllables[source_name] = result["syllables"]

        # Sample syllables across sources
        if len(all_syllables) == 1:
            source_name = list(all_syllables.keys())[0]
            selected = _sample_syllables(
                all_syllables[source_name], target_duration, rng
            )
        else:
            selected = _sample_syllables_multi_source(
                all_syllables, target_duration, rng
            )

        # Group syllables into clips
        clips = []
        for i in range(0, len(selected), syllables_per_clip):
            group = selected[i:i + syllables_per_clip]
            if not group:
                continue

            clip_start = min(s.start for s in group)
            clip_end = max(s.end for s in group)
            source = group[0].source if hasattr(group[0], "source") else group[0].word
            # Find which source file this syllable came from
            clip_source = "unknown"
            for src_name, src_syls in all_syllables.items():
                if group[0] in src_syls:
                    clip_source = src_name
                    break

            clip_idx = len(clips) + 1
            w_idx = group[0].word_index
            s_idx = 0  # syllable index within word
            filename = f"{clip_idx:03d}_{clip_source}_w{w_idx:02d}_s{s_idx:02d}.ogg"
            output_path = clips_dir / filename

            clips.append(Clip(
                syllables=group,
                start=clip_start,
                end=clip_end,
                source=clip_source,
                output_path=output_path,
            ))

        # Cut each clip from its source audio
        for clip in clips:
            source_audio = tmpdir / f"{clip.source}.wav"
            if source_audio.exists():
                cut_clip(
                    input_path=source_audio,
                    output_path=clip.output_path,
                    start=clip.syllables[0].start,
                    end=clip.syllables[-1].end,
                    padding_ms=padding_ms,
                    fade_ms=10,
                )

        # Generate gap durations
        gap_durations = []
        if len(clips) > 1:
            for _ in range(len(clips) - 1):
                gap_durations.append(rng.uniform(gap_min, gap_max))

        # Concatenate
        concatenated_path = output_dir / "concatenated.ogg"
        clip_paths = [c.output_path for c in clips if c.output_path.exists()]
        if clip_paths:
            concatenate_clips(
                clip_paths,
                concatenated_path,
                crossfade_ms=crossfade_ms,
                gap_durations_ms=gap_durations if gap_durations else None,
            )

        # Create zip of individual clips
        zip_path = output_dir / "clips.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for clip in clips:
                if clip.output_path.exists():
                    zf.write(clip.output_path, clip.output_path.name)

        # Write manifest
        manifest = {
            "sources": list(all_syllables.keys()),
            "total_syllables": sum(len(s) for s in all_syllables.values()),
            "selected_syllables": len(selected),
            "clips": [
                {
                    "filename": c.output_path.name,
                    "source": c.source,
                    "word": c.syllables[0].word if c.syllables else "",
                    "word_index": c.syllables[0].word_index if c.syllables else 0,
                    "start": c.start,
                    "end": c.end,
                }
                for c in clips
            ],
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

    transcript = "\n".join(all_transcripts)
    return Result(
        clips=clips,
        concatenated=concatenated_path,
        transcript=transcript,
        manifest=manifest,
    )
```

**Step 4: Run tests**

```bash
cd glottisdale && pytest tests/test_pipeline.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): pipeline orchestrator with sampling and concatenation"
```

---

### Task 8: CLI

**Files:**
- Create: `glottisdale/src/glottisdale/cli.py`
- Create: `glottisdale/tests/test_cli.py`

**Step 1: Write the test**

```python
"""Tests for CLI argument parsing."""

import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

from glottisdale.cli import parse_args


def test_parse_local_files():
    args = parse_args(["file1.mp4", "file2.wav"])
    assert args.input_files == ["file1.mp4", "file2.wav"]


def test_parse_defaults():
    args = parse_args([])
    assert args.output_dir == "./glottisdale-output"
    assert args.syllables_per_clip == 1
    assert args.target_duration == 10.0
    assert args.crossfade == 10
    assert args.padding == 25
    assert args.gap == "50-200"
    assert args.whisper_model == "base"
    assert args.aligner == "default"
    assert args.seed is None


def test_parse_all_options():
    args = parse_args([
        "--output-dir", "/tmp/out",
        "--syllables-per-clip", "3",
        "--target-duration", "30.0",
        "--crossfade", "0",
        "--padding", "50",
        "--gap", "100-500",
        "--whisper-model", "small",
        "--aligner", "default",
        "--seed", "42",
        "input.mp4",
    ])
    assert args.output_dir == "/tmp/out"
    assert args.syllables_per_clip == 3
    assert args.target_duration == 30.0
    assert args.crossfade == 0
    assert args.padding == 50
    assert args.gap == "100-500"
    assert args.whisper_model == "small"
    assert args.seed == 42
    assert args.input_files == ["input.mp4"]


def test_parse_slack_options():
    args = parse_args([
        "--source-channel", "#test-channel",
        "--dest-channel", "#output",
        "--max-videos", "3",
        "--dry-run",
        "--no-post",
    ])
    assert args.source_channel == "#test-channel"
    assert args.dest_channel == "#output"
    assert args.max_videos == 3
    assert args.dry_run is True
    assert args.no_post is True
```

**Step 2: Run to verify failure**

```bash
cd glottisdale && pytest tests/test_cli.py -v
```

**Step 3: Implement cli.py**

```python
"""CLI entrypoint for glottisdale."""

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="glottisdale",
        description="Syllable-level audio collage tool",
    )

    # Positional: input files (optional — if omitted, uses Slack)
    parser.add_argument(
        "input_files", nargs="*", default=[],
        help="Local video/audio files. If omitted, fetches from Slack.",
    )

    # Core options
    parser.add_argument("--output-dir", default="./glottisdale-output",
                        help="Output directory (default: ./glottisdale-output)")
    parser.add_argument("--syllables-per-clip", type=int, default=1,
                        help="Syllables per clip (default: 1)")
    parser.add_argument("--target-duration", type=float, default=10.0,
                        help="Target total duration in seconds (default: 10)")
    parser.add_argument("--crossfade", type=float, default=10,
                        help="Crossfade between clips in ms (default: 10, 0=hard cut)")
    parser.add_argument("--padding", type=float, default=25,
                        help="Padding around syllable cuts in ms (default: 25)")
    parser.add_argument("--gap", default="50-200",
                        help="Silence between clips in ms: '0', '100', or '50-200' (default: 50-200)")
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--aligner", default="default",
                        help="Alignment backend (default: default)")
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed for reproducible output")

    # Slack options
    parser.add_argument("--source-channel", default="#sample-sale",
                        help="Slack channel to pull videos from (default: #sample-sale)")
    parser.add_argument("--dest-channel", default="#glottisdale",
                        help="Slack channel to post results to (default: #glottisdale)")
    parser.add_argument("--max-videos", type=int, default=5,
                        help="Max source videos from Slack (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Process but don't post to Slack")
    parser.add_argument("--no-post", action="store_true",
                        help="Skip Slack posting, just write to output-dir")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    args = parse_args(argv)

    if args.input_files:
        # Local mode
        from glottisdale import process

        input_paths = [Path(f) for f in args.input_files]
        for p in input_paths:
            if not p.exists():
                print(f"Error: file not found: {p}", file=sys.stderr)
                sys.exit(1)

        result = process(
            input_paths=input_paths,
            output_dir=args.output_dir,
            syllables_per_clip=args.syllables_per_clip,
            target_duration=args.target_duration,
            crossfade_ms=args.crossfade,
            padding_ms=args.padding,
            gap=args.gap,
            aligner=args.aligner,
            whisper_model=args.whisper_model,
            seed=args.seed,
        )

        # Print summary to stdout
        print(f"Processed {len(args.input_files)} source file(s)")
        print(f"Transcript: {result.transcript}")
        print(f"Selected {len(result.clips)} clips")
        print(f"Output:")
        for clip in result.clips:
            print(f"  {clip.output_path.name}")
        print(f"  {result.concatenated.name}")
        print(f"  clips.zip")
    else:
        # Slack mode
        try:
            from glottisdale_slack.fetch import fetch_videos
            from glottisdale_slack.post import post_results
        except ImportError:
            print("Error: Slack mode requires slack extras: pip install glottisdale[slack]",
                  file=sys.stderr)
            sys.exit(1)

        import os
        import tempfile

        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            print("Error: SLACK_BOT_TOKEN environment variable required", file=sys.stderr)
            sys.exit(1)

        with tempfile.TemporaryDirectory() as tmpdir:
            videos = fetch_videos(
                token=token,
                channel=args.source_channel,
                max_videos=args.max_videos,
                download_dir=Path(tmpdir),
            )

            if not videos:
                print("No videos found in channel", file=sys.stderr)
                sys.exit(1)

            from glottisdale import process

            result = process(
                input_paths=[v["path"] for v in videos],
                output_dir=args.output_dir,
                syllables_per_clip=args.syllables_per_clip,
                target_duration=args.target_duration,
                crossfade_ms=args.crossfade,
                padding_ms=args.padding,
                gap=args.gap,
                aligner=args.aligner,
                whisper_model=args.whisper_model,
                seed=args.seed,
            )

            # Print summary
            print(f"Processed {len(videos)} source video(s), extracted {len(result.clips)} syllable clips")
            print("Sources:")
            for v in videos:
                syl_count = len([c for c in result.clips if c.source == Path(v["path"]).stem])
                link = v.get("permalink", "")
                print(f"  - {Path(v['path']).name} ({syl_count} syllables) {link}")
            print(f"Output:")
            print(f"  {result.concatenated}")
            print(f"  clips.zip")

            if not args.dry_run and not args.no_post:
                post_results(
                    token=token,
                    channel=args.dest_channel,
                    result=result,
                    sources=videos,
                    output_dir=Path(args.output_dir),
                )


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

```bash
cd glottisdale && pytest tests/test_cli.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/cli.py glottisdale/tests/test_cli.py
git commit -m "feat(glottisdale): CLI with local and Slack modes"
```

---

### Task 9: Slack Fetch Module

**Files:**
- Create: `glottisdale/slack/glottisdale_slack/__init__.py`
- Create: `glottisdale/slack/glottisdale_slack/fetch.py`
- Create: `glottisdale/tests/test_slack_fetch.py`

**Step 1: Write the test**

```python
"""Tests for Slack video fetching."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from glottisdale_slack.fetch import (
    find_channel_id,
    find_video_messages,
    fetch_videos,
)


def test_find_channel_id():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [
            {"name": "general", "id": "C001"},
            {"name": "sample-sale", "id": "C002"},
        ],
        "response_metadata": {"next_cursor": ""},
    }
    assert find_channel_id(client, "#sample-sale") == "C002"
    assert find_channel_id(client, "sample-sale") == "C002"


def test_find_channel_id_not_found():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [{"name": "general", "id": "C001"}],
        "response_metadata": {"next_cursor": ""},
    }
    assert find_channel_id(client, "#nonexistent") is None


def test_find_video_messages():
    client = MagicMock()
    client.conversations_history.return_value = {
        "messages": [
            {
                "ts": "123.456",
                "text": "check this out",
                "files": [
                    {"mimetype": "video/mp4", "url_private_download": "https://example.com/v.mp4",
                     "name": "clip.mp4", "id": "F001"},
                ],
            },
            {
                "ts": "789.012",
                "text": "a photo",
                "files": [
                    {"mimetype": "image/png", "url_private_download": "https://example.com/i.png",
                     "name": "pic.png", "id": "F002"},
                ],
            },
            {"ts": "345.678", "text": "no files"},
        ],
        "response_metadata": {"next_cursor": ""},
    }

    videos = find_video_messages(client, "C001")
    assert len(videos) == 1
    assert videos[0]["file"]["name"] == "clip.mp4"
    assert videos[0]["ts"] == "123.456"
```

**Step 2: Run to verify failure**

```bash
cd glottisdale && PYTHONPATH=glottisdale/slack pytest tests/test_slack_fetch.py -v
```

**Step 3: Implement fetch.py**

Follows existing codebase patterns: cursor pagination, `_download_with_auth`, video mimetype filtering.

```python
"""Fetch video files from a Slack channel."""

import logging
import random
from pathlib import Path

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Resolve channel name to ID via cursor pagination."""
    name = channel_name.lstrip("#")
    cursor = None
    while True:
        kwargs = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return None


def find_video_messages(client: WebClient, channel_id: str) -> list[dict]:
    """Find all messages with video attachments in a channel."""
    videos = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)
        for msg in resp.get("messages", []):
            for f in msg.get("files", []):
                if f.get("mimetype", "").startswith("video/"):
                    videos.append({
                        "file": f,
                        "ts": msg["ts"],
                        "text": msg.get("text", ""),
                    })
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return videos


def _download_with_auth(url: str, token: str, timeout: int = 60) -> requests.Response:
    """Download a file, manually following redirects to preserve auth."""
    headers = {"Authorization": f"Bearer {token}"}
    max_redirects = 5
    for _ in range(max_redirects):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp
    raise requests.TooManyRedirects(f"Too many redirects for {url}")


def fetch_videos(
    token: str,
    channel: str,
    max_videos: int,
    download_dir: Path,
) -> list[dict]:
    """Fetch random video files from a Slack channel.

    Returns:
        List of dicts with 'path' (Path to downloaded file) and 'permalink' keys.
    """
    client = WebClient(token=token)

    channel_id = find_channel_id(client, channel)
    if not channel_id:
        raise ValueError(f"Channel not found: {channel}")

    video_msgs = find_video_messages(client, channel_id)
    if not video_msgs:
        return []

    # Random sample
    selected = random.sample(video_msgs, min(max_videos, len(video_msgs)))

    results = []
    for msg in selected:
        f = msg["file"]
        url = f["url_private_download"]
        name = f.get("name", f"video_{f['id']}.mp4")
        dest = download_dir / name

        logger.info(f"Downloading {name}...")
        resp = _download_with_auth(url, token)

        # Validate content type
        content_type = resp.headers.get("Content-Type", "")
        if "video" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"Unexpected content type for {name}: {content_type}, skipping")
            continue

        dest.write_bytes(resp.content)

        permalink = f"https://slack.com/archives/{channel_id}/p{msg['ts'].replace('.', '')}"
        results.append({
            "path": dest,
            "permalink": permalink,
            "name": name,
            "file_id": f["id"],
        })

    return results
```

**Step 4: Create `__init__.py`**

```python
"""Glottisdale Slack integration."""
```

**Step 5: Run tests**

```bash
cd glottisdale && PYTHONPATH=glottisdale/slack pytest tests/test_slack_fetch.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add glottisdale/slack/ glottisdale/tests/test_slack_fetch.py
git commit -m "feat(glottisdale): Slack video fetching with auth and pagination"
```

---

### Task 10: Slack Post Module

**Files:**
- Create: `glottisdale/slack/glottisdale_slack/post.py`
- Create: `glottisdale/tests/test_slack_post.py`

**Step 1: Write the test**

```python
"""Tests for Slack posting."""

from pathlib import Path
from unittest.mock import MagicMock, call

from glottisdale_slack.post import post_results
from glottisdale.types import Result, Clip, Syllable, Phoneme


def test_post_results():
    client = MagicMock()
    client.chat_postMessage.return_value = {
        "ts": "111.222",
        "channel": "C999",
    }

    result = Result(
        clips=[
            Clip(
                syllables=[Syllable([Phoneme("AH0", 0.0, 0.1)], 0.0, 0.1, "test", 0)],
                start=0.0, end=0.1, source="video1",
                output_path=Path("/tmp/clips/001_video1_w00_s00.ogg"),
            ),
        ],
        concatenated=Path("/tmp/concatenated.ogg"),
        transcript="test",
        manifest={},
    )

    sources = [{"name": "video1.mp4", "permalink": "https://slack.com/archives/C001/p123"}]

    # Mock file existence
    post_results(
        token="xoxb-test",
        channel="#glottisdale",
        result=result,
        sources=sources,
        output_dir=Path("/tmp"),
        _client=client,  # inject mock
    )

    # Should post summary message
    client.chat_postMessage.assert_called_once()
    msg_text = client.chat_postMessage.call_args[1]["text"]
    assert "video1.mp4" in msg_text
    assert "1 syllable clips" in msg_text or "1 clips" in msg_text
```

**Step 2: Run to verify failure**

```bash
cd glottisdale && PYTHONPATH=glottisdale/slack pytest tests/test_slack_post.py -v
```

**Step 3: Implement post.py**

```python
"""Post glottisdale results to a Slack channel."""

import logging
from pathlib import Path

from slack_sdk import WebClient

from glottisdale.types import Result

logger = logging.getLogger(__name__)


def post_results(
    token: str,
    channel: str,
    result: Result,
    sources: list[dict],
    output_dir: Path,
    _client: WebClient | None = None,
) -> None:
    """Post concatenated audio + clips zip to a Slack channel.

    Posts a summary message, uploads concatenated.ogg to the thread,
    and uploads clips.zip as a threaded reply.
    """
    client = _client or WebClient(token=token)

    # Build summary text
    lines = [f":scissors: *Glottisdale* — {len(result.clips)} syllable clips"]
    lines.append("")
    lines.append("*Sources:*")
    for src in sources:
        name = src.get("name", "unknown")
        link = src.get("permalink", "")
        clip_count = len([c for c in result.clips if c.source == Path(name).stem])
        if link:
            lines.append(f"  - <{link}|{name}> ({clip_count} clips)")
        else:
            lines.append(f"  - {name} ({clip_count} clips)")

    summary = "\n".join(lines)

    # Post summary
    resp = client.chat_postMessage(channel=channel, text=summary)
    thread_ts = resp["ts"]
    channel_id = resp["channel"]

    # Upload concatenated audio
    concat_path = result.concatenated
    if concat_path.exists():
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=str(concat_path),
                filename="glottisdale.ogg",
                initial_comment="Concatenated syllable collage",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.exception("Failed to upload concatenated audio")

    # Upload clips zip
    zip_path = output_dir / "clips.zip"
    if zip_path.exists():
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=str(zip_path),
                filename="clips.zip",
                initial_comment="Individual syllable clips",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.exception("Failed to upload clips zip")
```

**Step 4: Run tests**

```bash
cd glottisdale && PYTHONPATH=glottisdale/slack pytest tests/test_slack_post.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add glottisdale/slack/glottisdale_slack/post.py glottisdale/tests/test_slack_post.py
git commit -m "feat(glottisdale): Slack posting with threaded uploads"
```

---

### Task 11: Bot Entrypoint for GitHub Actions

**Files:**
- Create: `glottisdale/bot.py`

This is a thin wrapper that ensures the Slack package path is importable and calls the CLI.

**Step 1: Write bot.py**

```python
"""GitHub Actions entrypoint for glottisdale.

Adds the slack/ subdirectory to sys.path so glottisdale_slack is importable,
then delegates to the CLI.
"""

import sys
from pathlib import Path

# Add slack package to path
slack_dir = Path(__file__).parent / "slack"
sys.path.insert(0, str(slack_dir))

from glottisdale.cli import main

if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add glottisdale/bot.py
git commit -m "feat(glottisdale): GitHub Actions bot entrypoint"
```

---

### Task 12: Requirements File

**Files:**
- Create: `glottisdale/requirements.txt`

**Step 1: Write requirements.txt**

Pinned dependencies for CI reproducibility. Note: torch and torchaudio are installed separately from the CPU index in the workflow.

```
openai-whisper>=20231117
g2p_en>=2.1.0
slack-sdk>=3.27.0
requests>=2.31.0
pytest>=8.0.0
```

**Step 2: Commit**

```bash
git add glottisdale/requirements.txt
git commit -m "chore(glottisdale): add requirements.txt for CI"
```

---

### Task 13: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/glottisdale.yml`

**Step 1: Write the workflow**

```yaml
name: Glottisdale

on:
  schedule:
    - cron: '0 18 * * *'  # 10am PT daily
  workflow_dispatch:
    inputs:
      target_duration:
        description: 'Target duration in seconds'
        default: '10'
      max_videos:
        description: 'Max source videos'
        default: '5'
      whisper_model:
        description: 'Whisper model (tiny/base/small)'
        default: 'base'
      seed:
        description: 'RNG seed (empty for random)'
        default: ''

jobs:
  glottisdale:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache Whisper + alignment models
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/whisper
            ~/.cache/torch
          key: glottisdale-models-${{ inputs.whisper_model || 'base' }}

      - name: Install system dependencies
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install Python dependencies
        run: |
          pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
          pip install -r glottisdale/requirements.txt
          pip install -e glottisdale/

      - name: Run glottisdale
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        run: |
          ARGS="--target-duration ${{ inputs.target_duration || '10' }}"
          ARGS="$ARGS --max-videos ${{ inputs.max_videos || '5' }}"
          ARGS="$ARGS --whisper-model ${{ inputs.whisper_model || 'base' }}"
          if [ -n "${{ inputs.seed }}" ]; then
            ARGS="$ARGS --seed ${{ inputs.seed }}"
          fi
          python glottisdale/bot.py $ARGS
```

**Step 2: Commit**

```bash
git add .github/workflows/glottisdale.yml
git commit -m "ci(glottisdale): daily workflow with model caching"
```

---

### Task 14: Integration Test (End-to-End Local Mode)

**Files:**
- Create: `glottisdale/tests/test_integration.py`

This test uses real ffmpeg but mocks Whisper (to avoid downloading the model in CI). It verifies the full pipeline from audio file to output directory.

**Step 1: Write the test**

Mark with `@pytest.mark.integration` so it can be run separately.

```python
"""Integration test: full pipeline with real ffmpeg, mocked Whisper."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from glottisdale import process


@pytest.mark.integration
@patch("glottisdale.align.transcribe")
def test_full_pipeline_local_mode(mock_transcribe, tmp_path):
    """End-to-end: generate test audio → process → verify output."""
    import subprocess

    # Generate a 3-second test WAV with speech-like characteristics
    input_wav = tmp_path / "input.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-ar", "16000", "-ac", "1",
        str(input_wav),
    ], capture_output=True, check=True)

    # Mock Whisper to return fake word timestamps
    mock_transcribe.return_value = {
        "text": "hello beautiful world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.8},
            {"word": "beautiful", "start": 0.9, "end": 1.8},
            {"word": "world", "start": 1.9, "end": 2.5},
        ],
        "language": "en",
    }

    output_dir = tmp_path / "output"
    result = process(
        input_paths=[input_wav],
        output_dir=output_dir,
        target_duration=5.0,
        crossfade_ms=0,
        padding_ms=10,
        gap="0",
        seed=42,
    )

    # Verify outputs exist
    assert output_dir.exists()
    assert (output_dir / "clips").is_dir()
    assert result.concatenated.exists()
    assert (output_dir / "clips.zip").exists()
    assert (output_dir / "manifest.json").exists()

    # Verify manifest
    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["sources"] == ["input"]
    assert len(manifest["clips"]) > 0

    # Verify clips are real OGG files
    for clip in result.clips:
        assert clip.output_path.exists()
        assert clip.output_path.stat().st_size > 0

    # "hello" = 2 syllables, "beautiful" = 3 syllables, "world" = 1 syllable = 6 total
    assert len(result.clips) >= 3  # at least some syllables selected
```

**Step 2: Run the integration test**

```bash
cd glottisdale && pytest tests/test_integration.py -v -m integration
```

Expected: PASS (requires ffmpeg installed locally).

**Step 3: Commit**

```bash
git add glottisdale/tests/test_integration.py
git commit -m "test(glottisdale): end-to-end integration test with mocked Whisper"
```

---

### Task 15: Update Design Doc and Memory

**Files:**
- Modify: `docs/plans/2026-02-15-glottisdale-design.md` — note ForceAlign finding and architecture change
- Modify: `~/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md` — add glottisdale section

**Step 1: Update design doc**

Add a note to the Aligner Interface section about the ForceAlign finding:

> **Architecture change (during implementation planning):** ForceAlign was dropped after discovering its phoneme timestamps are evenly divided across the word duration (not truly force-aligned). The default backend uses Whisper word timestamps + g2p_en + vendored syllabify instead, which produces identical phoneme timing with fewer dependencies. The aligner interface is retained for future BFA integration.

**Step 2: Update MEMORY.md**

Add a `## Glottisdale` section to MEMORY.md with key conventions.

**Step 3: Commit**

```bash
git add docs/plans/2026-02-15-glottisdale-design.md
git commit -m "docs: update glottisdale design with ForceAlign finding and architecture change"
```

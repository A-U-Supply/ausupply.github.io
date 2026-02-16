# Hymnal Gargler Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily bot that pitch-maps Glottisdale syllable collages to MIDI melodies, producing "singing" with rubberband-based pitch shifting, vibrato, chorus layering, and Magenta.js melody extension.

**Architecture:** Standalone `hymnal-gargler/` directory. Fetches MIDI from #midieval + videos from #sample-sale. Uses glottisdale library (via importlib) for syllabification, ffmpeg rubberband for pitch/time manipulation, Magenta.js for melody extension. Posts two tracks (full mix + a cappella) to #glottisdale.

**Tech Stack:** Python 3.13, Node 18 (Magenta.js), ffmpeg with librubberband, pretty_midi, glottisdale library, slack-sdk

---

### Task 1: Project Scaffolding

**Files:**
- Create: `hymnal-gargler/requirements.txt`
- Create: `hymnal-gargler/package.json`
- Create: `hymnal-gargler/__init__.py`

**Step 1: Create directory and Python dependencies**

```bash
mkdir -p hymnal-gargler
```

Write `hymnal-gargler/requirements.txt`:
```
pretty_midi>=0.2.10
slack-sdk>=3.27.0
requests>=2.31.0
numpy>=1.24.0
scipy>=1.10.0
```

**Step 2: Create Node.js package for Magenta.js**

Write `hymnal-gargler/package.json`:
```json
{
  "name": "hymnal-gargler",
  "private": true,
  "type": "commonjs",
  "dependencies": {
    "@magenta/music": "^1.23.1",
    "@tonejs/midi": "^2.0.28"
  },
  "overrides": {
    "tone": "14.8.26"
  }
}
```

**Step 3: Create empty `__init__.py`**

Write `hymnal-gargler/__init__.py`:
```python
```

**Step 4: Commit**

```bash
git add hymnal-gargler/
git commit -m "chore: scaffold hymnal-gargler project"
```

---

### Task 2: MIDI Parser

Parse MIDI files into structured note sequences using pretty_midi.

**Files:**
- Create: `hymnal-gargler/midi_parser.py`
- Create: `hymnal-gargler/tests/test_midi_parser.py`

**Step 1: Write the failing test**

Write `hymnal-gargler/tests/__init__.py` (empty) and `hymnal-gargler/tests/test_midi_parser.py`:

```python
"""Tests for MIDI parser."""
import tempfile
from pathlib import Path

import pretty_midi

from hymnal_gargler.midi_parser import parse_midi, Note


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
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/jake/au-supply/ausupply.github.io
PYTHONPATH=hymnal-gargler python -m pytest hymnal-gargler/tests/test_midi_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'hymnal_gargler'`

**Step 3: Write minimal implementation**

Write `hymnal-gargler/midi_parser.py`:

```python
"""Parse MIDI files into structured note sequences."""
from dataclasses import dataclass
from pathlib import Path

import pretty_midi


@dataclass
class Note:
    """A single MIDI note."""
    pitch: int
    start: float
    end: float
    velocity: int

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class MidiTrack:
    """Parsed MIDI track."""
    notes: list[Note]
    tempo: float
    program: int
    is_drum: bool
    total_duration: float


def parse_midi(path: Path) -> MidiTrack:
    """Parse a MIDI file into a MidiTrack."""
    mid = pretty_midi.PrettyMIDI(str(path))

    tempo = mid.estimate_tempo()
    notes = []
    program = 0
    is_drum = False

    if mid.instruments:
        inst = mid.instruments[0]
        program = inst.program
        is_drum = inst.is_drum
        for n in sorted(inst.notes, key=lambda n: n.start):
            notes.append(Note(
                pitch=n.pitch,
                start=round(n.start, 4),
                end=round(n.end, 4),
                velocity=n.velocity,
            ))

    total_duration = mid.get_end_time()
    return MidiTrack(
        notes=notes,
        tempo=round(tempo),
        program=program,
        is_drum=is_drum,
        total_duration=total_duration,
    )
```

Note: the module needs to be importable as `hymnal_gargler`, so we also need to make the directory importable. Since the directory is named `hymnal-gargler` (with a hyphen), we need to set up PYTHONPATH correctly. The tests import `from hymnal_gargler.midi_parser import ...`, but the directory has a hyphen.

**Fix:** Rename the Python source to a subdirectory, or use the project root approach. Simplest: keep all Python modules in `hymnal-gargler/` and add it to `PYTHONPATH`, but import as `midi_parser` directly. Update test imports:

Actually, follow the same pattern as other bots (midi-bot, puke-box) — flat directory, no package nesting. Update tests to use `sys.path` insertion:

Update `hymnal-gargler/tests/test_midi_parser.py` imports to:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from midi_parser import parse_midi, Note
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest hymnal-gargler/tests/test_midi_parser.py -v
```

Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/midi_parser.py hymnal-gargler/tests/
git commit -m "feat(hymnal-gargler): add MIDI parser"
```

---

### Task 3: Syllable Preparation

Import glottisdale library and build a syllable pool from video/audio files. Transcribe, syllabify, cut clips, normalize F0 and volume.

**Files:**
- Create: `hymnal-gargler/syllable_prep.py`
- Create: `hymnal-gargler/tests/test_syllable_prep.py`

**Step 1: Write the failing test**

Write `hymnal-gargler/tests/test_syllable_prep.py`:

```python
"""Tests for syllable preparation."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

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
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest hymnal-gargler/tests/test_syllable_prep.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Write `hymnal-gargler/syllable_prep.py`:

```python
"""Prepare syllable clips from audio/video sources using glottisdale library."""
import importlib.util
import logging
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import median

logger = logging.getLogger(__name__)

# Base path for sibling project imports
_BASE = Path(__file__).parent.parent


def _import_glottisdale_module(module_name):
    """Import a glottisdale module via importlib."""
    mod_path = _BASE / "glottisdale" / "src" / "glottisdale" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"glottisdale_{module_name}", mod_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@dataclass
class NormalizedSyllable:
    """A pitch- and volume-normalized syllable clip."""
    clip_path: Path
    f0: float | None
    duration: float
    phonemes: list[str]
    word: str


def compute_pitch_shifts(f0_values: list[float | None]) -> list[float]:
    """Compute semitone shifts to normalize all F0s to the median.

    Returns a list of shifts in semitones (same length as input).
    None values get 0 shift.
    """
    voiced = [f for f in f0_values if f is not None and f > 0]
    if not voiced:
        return [0.0] * len(f0_values)

    target = median(voiced)
    shifts = []
    for f0 in f0_values:
        if f0 is None or f0 <= 0:
            shifts.append(0.0)
        else:
            shifts.append(12 * math.log2(target / f0))
    return shifts


def prepare_syllables(
    input_paths: list[Path],
    work_dir: Path,
    whisper_model: str = "base",
    max_semitone_shift: float = 5.0,
) -> list[NormalizedSyllable]:
    """Full pipeline: transcribe, syllabify, cut, normalize.

    Args:
        input_paths: Video or audio files to process.
        work_dir: Working directory for intermediate files.
        whisper_model: Whisper model size.
        max_semitone_shift: Maximum pitch normalization shift.

    Returns:
        List of NormalizedSyllable with normalized clips.
    """
    audio_mod = _import_glottisdale_module("audio")
    transcribe_mod = _import_glottisdale_module("transcribe")
    syllabify_mod = _import_glottisdale_module("syllabify")
    analysis_mod = _import_glottisdale_module("analysis")

    clips_dir = work_dir / "syllable_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    all_syllables = []
    clip_index = 0

    for input_path in input_paths:
        # Extract audio
        wav_path = work_dir / f"{input_path.stem}_audio.wav"
        audio_mod.extract_audio(input_path, wav_path)

        # Transcribe
        result = transcribe_mod.transcribe(wav_path, model_name=whisper_model)
        words = result.get("words", [])
        if not words:
            logger.warning(f"No words transcribed from {input_path}")
            continue

        # Syllabify
        syllables = syllabify_mod.syllabify_words(words)
        logger.info(f"{input_path.name}: {len(syllables)} syllables")

        # Cut each syllable
        for syl in syllables:
            clip_path = clips_dir / f"syl_{clip_index:04d}.wav"
            audio_mod.cut_clip(wav_path, clip_path, syl.start, syl.end, padding_ms=25)

            # Estimate F0
            samples, sr = analysis_mod.read_wav(clip_path)
            f0 = analysis_mod.estimate_f0(samples, sr)
            duration = audio_mod.get_duration(clip_path)

            phoneme_labels = [p.label for p in syl.phonemes]
            all_syllables.append(NormalizedSyllable(
                clip_path=clip_path,
                f0=f0,
                duration=duration,
                phonemes=phoneme_labels,
                word=syl.word,
            ))
            clip_index += 1

    if not all_syllables:
        raise ValueError("No syllables extracted from any input file")

    # Normalize pitch to median F0
    f0_values = [s.f0 for s in all_syllables]
    shifts = compute_pitch_shifts(f0_values)
    for syl, shift in zip(all_syllables, shifts):
        if abs(shift) < 0.1:
            continue
        clamped = max(-max_semitone_shift, min(max_semitone_shift, shift))
        normalized_path = syl.clip_path.with_suffix(".norm.wav")
        _rubberband_pitch_shift(syl.clip_path, normalized_path, clamped)
        if normalized_path.exists():
            syl.clip_path = normalized_path

    # Volume normalize to median RMS
    rms_values = []
    for syl in all_syllables:
        samples, sr = analysis_mod.read_wav(syl.clip_path)
        rms = analysis_mod.compute_rms(samples)
        rms_values.append(rms)

    voiced_rms = [r for r in rms_values if r > 0]
    if voiced_rms:
        target_rms = median(voiced_rms)
        for syl, rms in zip(all_syllables, rms_values):
            if rms <= 0:
                continue
            db_adjust = 20 * math.log10(target_rms / rms)
            db_adjust = max(-20, min(20, db_adjust))
            if abs(db_adjust) < 0.5:
                continue
            vol_path = syl.clip_path.with_suffix(".vol.wav")
            audio_mod.adjust_volume(syl.clip_path, vol_path, db_adjust)
            if vol_path.exists():
                syl.clip_path = vol_path
                syl.duration = audio_mod.get_duration(vol_path)

    return all_syllables


def _rubberband_pitch_shift(input_path: Path, output_path: Path, semitones: float):
    """Pitch shift using ffmpeg rubberband filter."""
    ratio = 2 ** (semitones / 12.0)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-filter:a", f"rubberband=pitch={ratio:.6f}",
            "-ar", "16000", str(output_path),
        ],
        capture_output=True,
    )
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest hymnal-gargler/tests/test_syllable_prep.py -v
```

Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/syllable_prep.py hymnal-gargler/tests/test_syllable_prep.py
git commit -m "feat(hymnal-gargler): add syllable preparation pipeline"
```

---

### Task 4: Vocal Mapper — Core Pitch & Time Logic

The heart of the bot. Maps syllables to melody notes with pitch shifting, time stretching, and rhythmic variation.

**Files:**
- Create: `hymnal-gargler/vocal_mapper.py`
- Create: `hymnal-gargler/tests/test_vocal_mapper.py`

**Step 1: Write the failing tests**

Write `hymnal-gargler/tests/test_vocal_mapper.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest hymnal-gargler/tests/test_vocal_mapper.py -v
```

Expected: FAIL

**Step 3: Write implementation**

Write `hymnal-gargler/vocal_mapper.py`:

```python
"""Map syllables to melody notes — the 'drunk choir' engine."""
import logging
import math
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pretty_midi

logger = logging.getLogger(__name__)


@dataclass
class NoteMapping:
    """How a melody note maps to syllable(s)."""
    note_pitch: int
    note_start: float
    note_end: float
    note_duration: float
    syllable_indices: list[int]
    pitch_shift_semitones: float
    time_stretch_ratio: float
    apply_vibrato: bool
    apply_chorus: bool
    duration_class: str  # "short", "medium", "long"


def compute_target_pitch(
    note_midi: int,
    source_f0: float,
    drift_semitones: float = 0,
) -> float:
    """Compute semitone shift from source F0 to target MIDI note (with optional drift).

    Args:
        note_midi: Target MIDI note number.
        source_f0: Source syllable's F0 in Hz (after normalization).
        drift_semitones: Signed drift to add (for loose pitch following).

    Returns:
        Shift in semitones.
    """
    target_hz = pretty_midi.note_number_to_hz(note_midi)
    base_shift = 12 * math.log2(target_hz / source_f0)
    return base_shift + drift_semitones


def classify_note_duration(duration: float) -> Literal["short", "medium", "long"]:
    """Classify a note by duration for mapping strategy."""
    if duration < 0.2:
        return "short"
    elif duration < 1.0:
        return "medium"
    else:
        return "long"


def plan_note_mapping(
    notes: list,
    pool_size: int,
    seed: int | None = None,
    drift_range: float = 2.0,
    chorus_probability: float = 0.3,
) -> list[NoteMapping]:
    """Plan how each melody note maps to syllable(s).

    Args:
        notes: List of Note objects from midi_parser.
        pool_size: Number of available syllables.
        seed: Random seed for reproducibility.
        drift_range: Max semitones of pitch drift from melody.
        chorus_probability: Probability of chorus on non-sustained notes.

    Returns:
        List of NoteMapping, one per note.
    """
    rng = random.Random(seed)
    mappings = []
    syl_cursor = 0

    for note in notes:
        duration = note.end - note.start
        dur_class = classify_note_duration(duration)

        # Determine how many syllables this note gets
        if dur_class == "short":
            n_syls = 1
        elif dur_class == "medium":
            n_syls = rng.choice([1, 1, 1, 2, 2, 3])  # weighted toward 1
        else:
            n_syls = rng.choice([1, 2, 2, 3, 3, 4])  # weighted toward 2-3

        # Assign syllable indices (cycle through pool)
        indices = []
        for _ in range(n_syls):
            indices.append(syl_cursor % pool_size)
            syl_cursor += 1

        # Pitch drift (weighted toward 0)
        drift = rng.gauss(0, drift_range / 3)
        drift = max(-drift_range, min(drift_range, drift))

        # Vibrato on held notes
        apply_vibrato = dur_class == "long" or (dur_class == "medium" and duration > 0.6)

        # Chorus on sustained notes, random chance otherwise
        apply_chorus = (
            duration > 0.6
            or rng.random() < chorus_probability
        )

        # Time stretch ratio: how much to speed/slow the syllable
        # Will be computed per-syllable during rendering (depends on clip duration)
        time_ratio = 1.0  # placeholder, computed at render time

        mappings.append(NoteMapping(
            note_pitch=note.pitch,
            note_start=note.start,
            note_end=note.end,
            note_duration=duration,
            syllable_indices=indices,
            pitch_shift_semitones=drift,  # drift only; base shift computed at render
            time_stretch_ratio=time_ratio,
            apply_vibrato=apply_vibrato,
            apply_chorus=apply_chorus,
            duration_class=dur_class,
        ))

    return mappings


def render_mapping(
    mapping: NoteMapping,
    syllable_clips: list,
    work_dir: Path,
    note_index: int,
    median_f0: float,
    max_shift: float = 12.0,
) -> Path | None:
    """Render a single note mapping to a WAV file.

    Args:
        mapping: The NoteMapping to render.
        syllable_clips: List of NormalizedSyllable objects.
        work_dir: Working directory for temp files.
        note_index: Index for unique filenames.
        median_f0: Median F0 of the normalized syllable pool.
        max_shift: Maximum pitch shift in semitones.

    Returns:
        Path to rendered WAV, or None on failure.
    """
    note_dir = work_dir / f"note_{note_index:04d}"
    note_dir.mkdir(exist_ok=True)

    target_duration = mapping.note_duration
    n_syls = len(mapping.syllable_indices)
    per_syl_duration = target_duration / n_syls

    # Add rhythmic variation: ±20% of exact duration
    import random as _rng
    syl_durations = []
    remaining = target_duration
    for i in range(n_syls):
        if i == n_syls - 1:
            syl_durations.append(remaining)
        else:
            variation = _rng.uniform(0.8, 1.2)
            d = per_syl_duration * variation
            d = min(d, remaining - 0.05 * (n_syls - i - 1))
            d = max(d, 0.05)
            syl_durations.append(d)
            remaining -= d

    rendered_parts = []
    for i, (syl_idx, syl_dur) in enumerate(zip(mapping.syllable_indices, syl_durations)):
        syl = syllable_clips[syl_idx]

        # Compute total pitch shift: base (median→note) + drift
        base_shift = compute_target_pitch(mapping.note_pitch, median_f0, mapping.pitch_shift_semitones)
        shift = max(-max_shift, min(max_shift, base_shift))

        # Time stretch: syllable duration → target per-syllable duration
        time_ratio = syl.duration / syl_dur if syl_dur > 0 else 1.0
        time_ratio = max(0.25, min(4.0, time_ratio))  # clamp

        # Apply rubberband pitch shift + time stretch
        part_path = note_dir / f"part_{i:02d}.wav"
        _rubberband_transform(syl.clip_path, part_path, shift, time_ratio)

        if not part_path.exists() or part_path.stat().st_size < 100:
            continue

        # Apply vibrato if flagged
        if mapping.apply_vibrato and syl_dur > 0.3:
            vibrato_path = note_dir / f"part_{i:02d}_vib.wav"
            _apply_vibrato(part_path, vibrato_path)
            if vibrato_path.exists():
                part_path = vibrato_path

        rendered_parts.append(part_path)

    if not rendered_parts:
        return None

    # Concatenate parts (intra-note crossfade)
    if len(rendered_parts) == 1:
        output = note_dir / "rendered.wav"
        subprocess.run(["cp", str(rendered_parts[0]), str(output)], capture_output=True)
    else:
        output = note_dir / "rendered.wav"
        _concat_with_crossfade(rendered_parts, output, crossfade_ms=20)

    # Apply chorus if flagged
    if mapping.apply_chorus and output.exists():
        chorus_path = note_dir / "rendered_chorus.wav"
        _apply_chorus(output, chorus_path)
        if chorus_path.exists():
            output = chorus_path

    return output if output.exists() else None


def render_vocal_track(
    mappings: list[NoteMapping],
    syllable_clips: list,
    work_dir: Path,
    median_f0: float,
    target_duration: float = 40.0,
) -> Path:
    """Render all mappings into a complete vocal track.

    Handles gaps between notes (portamento or silence/room-tone).

    Returns:
        Path to the final a cappella WAV.
    """
    render_dir = work_dir / "vocal_render"
    render_dir.mkdir(exist_ok=True)

    rendered_notes = []
    for i, mapping in enumerate(mappings):
        result = render_mapping(mapping, syllable_clips, render_dir, i, median_f0)
        if result:
            rendered_notes.append((mapping, result))

    if not rendered_notes:
        raise ValueError("No notes rendered successfully")

    # Build timeline: place rendered notes at their start times with gaps
    # Use silence for gaps, portamento between adjacent notes
    parts_with_gaps = []
    for idx, (mapping, wav_path) in enumerate(rendered_notes):
        if idx > 0:
            prev_mapping = rendered_notes[idx - 1][0]
            gap_duration = mapping.note_start - prev_mapping.note_end
            if gap_duration > 0.01:
                # Insert silence/room-tone gap
                gap_path = render_dir / f"gap_{idx:04d}.wav"
                gap_ms = gap_duration * 1000
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"anullsrc=r=16000:cl=mono",
                    "-t", str(gap_duration),
                    "-ar", "16000", str(gap_path),
                ], capture_output=True)
                if gap_path.exists():
                    parts_with_gaps.append(gap_path)

        parts_with_gaps.append(wav_path)

    # Concatenate everything with crossfade for smoothness
    output_path = work_dir / "acappella.wav"
    if len(parts_with_gaps) == 1:
        subprocess.run(["cp", str(parts_with_gaps[0]), str(output_path)], capture_output=True)
    else:
        _concat_with_crossfade(parts_with_gaps, output_path, crossfade_ms=30)

    return output_path


def _rubberband_transform(input_path: Path, output_path: Path, semitones: float, tempo_ratio: float):
    """Combined pitch shift + time stretch via ffmpeg rubberband."""
    pitch_ratio = 2 ** (semitones / 12.0)
    tempo_ratio = max(0.25, min(4.0, tempo_ratio))
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter:a", f"rubberband=pitch={pitch_ratio:.6f}:tempo={tempo_ratio:.4f}",
        "-ar", "16000", str(output_path),
    ], capture_output=True)


def _apply_vibrato(input_path: Path, output_path: Path, depth_cents: float = 50, rate_hz: float = 5.5):
    """Apply vibrato via ffmpeg vibrato filter.

    depth_cents: ±cents of pitch wobble (50 cents = 0.5 semitone)
    rate_hz: oscillation speed
    """
    # ffmpeg vibrato: depth is 0-1 (fraction of semitone), f is rate
    depth = min(depth_cents / 100.0, 1.0)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter:a", f"vibrato=f={rate_hz}:d={depth:.3f}",
        "-ar", "16000", str(output_path),
    ], capture_output=True)


def _apply_chorus(input_path: Path, output_path: Path, n_voices: int = 2):
    """Layer detuned copies for chorus effect.

    Creates n_voices copies with slight pitch offset (±10-15 cents)
    and time offset (15-30ms), mixed at lower volume.
    """
    import random as _rng

    voices = [input_path]  # original
    work_dir = output_path.parent

    for v in range(n_voices):
        detune_cents = _rng.uniform(10, 15) * _rng.choice([-1, 1])
        detune_ratio = 2 ** (detune_cents / 1200.0)
        delay_ms = _rng.uniform(15, 30)

        voice_path = work_dir / f"chorus_voice_{v}.wav"
        # Detune
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-filter:a", f"rubberband=pitch={detune_ratio:.6f},adelay={delay_ms:.0f}|{delay_ms:.0f}",
            "-ar", "16000", str(voice_path),
        ], capture_output=True)
        if voice_path.exists():
            voices.append(voice_path)

    if len(voices) == 1:
        subprocess.run(["cp", str(input_path), str(output_path)], capture_output=True)
        return

    # Mix all voices: original at full volume, chorus at -6dB
    inputs = []
    for v in voices:
        inputs.extend(["-i", str(v)])

    weights = ["1"] + ["0.5"] * (len(voices) - 1)
    weight_str = " ".join(weights)

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex",
        f"amix=inputs={len(voices)}:duration=shortest:weights={weight_str}",
        "-ar", "16000", str(output_path),
    ], capture_output=True)


def _concat_with_crossfade(clip_paths: list[Path], output_path: Path, crossfade_ms: float = 25):
    """Concatenate clips with crossfade, pairwise."""
    from syllable_prep import _rubberband_pitch_shift  # avoid circular, just need ffmpeg

    current = clip_paths[0]
    for i in range(1, len(clip_paths)):
        out = output_path.parent / f"_concat_temp_{i}.wav"

        # Get durations to avoid crossfade longer than clips
        dur_a = _get_duration(current)
        dur_b = _get_duration(clip_paths[i])
        cf_s = crossfade_ms / 1000.0
        cf_s = min(cf_s, dur_a * 0.4, dur_b * 0.4)

        if cf_s > 0.005:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(current), "-i", str(clip_paths[i]),
                "-filter_complex", f"acrossfade=d={cf_s:.4f}:c1=tri:c2=tri",
                "-ar", "16000", str(out),
            ], capture_output=True)
        else:
            # Just concat without crossfade
            list_file = output_path.parent / f"_concat_list_{i}.txt"
            list_file.write_text(f"file '{current}'\nfile '{clip_paths[i]}'\n")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-ar", "16000", "-c:a", "pcm_s16le", str(out),
            ], capture_output=True)

        if out.exists() and out.stat().st_size > 100:
            current = out

    subprocess.run(["cp", str(current), str(output_path)], capture_output=True)

    # Cleanup temp files
    for f in output_path.parent.glob("_concat_*"):
        f.unlink(missing_ok=True)


def _get_duration(path: Path) -> float:
    """Get audio duration via ffprobe."""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest hymnal-gargler/tests/test_vocal_mapper.py -v
```

Expected: 6 tests PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/vocal_mapper.py hymnal-gargler/tests/test_vocal_mapper.py
git commit -m "feat(hymnal-gargler): add vocal mapper with pitch, time, vibrato, chorus"
```

---

### Task 5: Magenta.js Melody Extension

Extend 4-bar MIDI tracks to ~40 seconds using Magenta.js models.

**Files:**
- Create: `hymnal-gargler/extend_midi.js`
- Create: `hymnal-gargler/extender.py`
- Create: `hymnal-gargler/tests/test_extender.py`

**Step 1: Write extend_midi.js**

Write `hymnal-gargler/extend_midi.js`:

```javascript
/**
 * Extend MIDI tracks using Magenta.js models.
 *
 * Reads params from stdin JSON:
 *   melodyMidi: path to melody.mid
 *   drumsMidi: path to drums.mid
 *   bassMidi: path to bass.mid
 *   chordsMidi: path to chords.mid
 *   outputDir: output directory
 *   targetDuration: target duration in seconds
 *   scale: scale name
 *   root: root note
 *   scaleIntervals: array of semitone intervals
 *   tempo: BPM
 *   chords: array of chord symbols
 *   temperature: base temperature (0.5-1.5)
 */

const fs = require('fs');
const path = require('path');
const mm = require('@magenta/music/node/music_rnn');
const core = require('@magenta/music/node/core');
const { Midi } = require('@tonejs/midi');

const IMPROV_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/chord_pitches_improv';
const DRUMS_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/drum_kit_rnn';
const STEPS_PER_QUARTER = 4;

function readMidi(filePath) {
    const data = fs.readFileSync(filePath);
    return new Midi(data);
}

function midiToNoteSequence(midi, isDrum = false) {
    const notes = [];
    for (const track of midi.tracks) {
        for (const note of track.notes) {
            notes.push({
                pitch: note.midi,
                startTime: note.time,
                endTime: note.time + note.duration,
                velocity: Math.round(note.velocity * 127),
                program: isDrum ? 0 : (track.instrument ? track.instrument.number : 0),
                instrument: 0,
                isDrum: isDrum,
            });
        }
    }
    return {
        ticksPerQuarter: 220,
        totalTime: Math.max(...notes.map(n => n.endTime), 0),
        tempos: [{ time: 0, qpm: midi.header.tempos[0]?.bpm || 120 }],
        timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
        notes: notes,
        controlChanges: [],
    };
}

function buildScalePitches(root, intervals, minPitch = 36, maxPitch = 96) {
    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const rootIdx = noteNames.indexOf(root.replace('b', '#')); // simplified
    const pitches = [];
    for (let octave = 0; octave < 10; octave++) {
        for (const interval of intervals) {
            const pitch = rootIdx + (octave * 12) + interval;
            if (pitch >= minPitch && pitch <= maxPitch) {
                pitches.push(pitch);
            }
        }
    }
    return [...new Set(pitches)].sort((a, b) => a - b);
}

function quantizeToScale(pitch, scalePitches) {
    let closest = scalePitches[0];
    let minDist = Math.abs(pitch - closest);
    for (const sp of scalePitches) {
        const dist = Math.abs(pitch - sp);
        if (dist < minDist) {
            minDist = dist;
            closest = sp;
        }
    }
    return closest;
}

async function extendMelody(seedSeq, params, scalePitches, targetBars) {
    const improvRnn = new mm.MusicRNN(IMPROV_CHECKPOINT);
    await improvRnn.initialize();

    const secondsPerBar = (60.0 / params.tempo) * 4;
    const stepsPerBar = STEPS_PER_QUARTER * 4;
    const allNotes = [...seedSeq.notes];
    let currentTime = seedSeq.totalTime;

    // Generate in 4-bar chunks, cycling temperature
    const baseBars = Math.ceil(seedSeq.totalTime / secondsPerBar);
    let barsGenerated = baseBars;

    while (barsGenerated < targetBars) {
        // Cycle temperature: some chunks repeat-ish (low temp), some explore (high temp)
        const cyclePos = (barsGenerated - baseBars) % 12;
        let temp;
        if (cyclePos < 4) temp = params.temperature * 0.6;      // repetitive
        else if (cyclePos < 8) temp = params.temperature * 1.0;  // moderate
        else temp = params.temperature * 1.3;                     // exploratory

        // Use last few notes as seed for continuation
        const recentNotes = allNotes.slice(-8).map(n => ({
            ...n,
            startTime: n.startTime - (currentTime - secondsPerBar),
            endTime: n.endTime - (currentTime - secondsPerBar),
        })).filter(n => n.startTime >= 0);

        const seed = {
            ticksPerQuarter: 220,
            totalTime: secondsPerBar,
            tempos: [{ time: 0, qpm: params.tempo }],
            timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
            notes: recentNotes.length > 0 ? recentNotes : [{
                pitch: scalePitches[Math.floor(scalePitches.length / 2)],
                startTime: 0, endTime: 0.5, velocity: 100,
                program: 0, instrument: 0, isDrum: false,
            }],
            controlChanges: [],
        };

        const quantizedSeed = core.sequences.quantizeNoteSequence(seed, STEPS_PER_QUARTER);
        const barsToGen = Math.min(4, targetBars - barsGenerated);
        const totalSteps = barsToGen * stepsPerBar;

        try {
            const continuation = await improvRnn.continueSequence(
                quantizedSeed, totalSteps, temp, params.chords
            );

            for (const note of continuation.notes) {
                allNotes.push({
                    pitch: quantizeToScale(note.pitch, scalePitches),
                    startTime: note.startTime + currentTime,
                    endTime: note.endTime + currentTime,
                    velocity: note.velocity || 100,
                    program: params.melodyInstrument || 0,
                    instrument: 0,
                    isDrum: false,
                });
            }
            currentTime += barsToGen * secondsPerBar;
        } catch (e) {
            console.error('Magenta continuation error, looping original:', e.message);
            // Fallback: loop original notes
            for (const note of seedSeq.notes) {
                allNotes.push({
                    ...note,
                    startTime: note.startTime + currentTime,
                    endTime: note.endTime + currentTime,
                });
            }
            currentTime += seedSeq.totalTime;
        }

        barsGenerated += 4;
    }

    improvRnn.dispose();

    return {
        ...seedSeq,
        notes: allNotes,
        totalTime: currentTime,
        controlChanges: [],
    };
}

async function extendDrums(seedSeq, params, targetBars) {
    const drumsRnn = new mm.MusicRNN(DRUMS_CHECKPOINT);
    await drumsRnn.initialize();

    const secondsPerBar = (60.0 / params.tempo) * 4;
    const stepsPerBar = STEPS_PER_QUARTER * 4;
    const allNotes = [...seedSeq.notes];
    let currentTime = seedSeq.totalTime;
    let barsGenerated = Math.ceil(seedSeq.totalTime / secondsPerBar);

    while (barsGenerated < targetBars) {
        const recentNotes = allNotes.slice(-8).map(n => ({
            ...n,
            startTime: Math.max(0, n.startTime - (currentTime - secondsPerBar)),
            endTime: Math.max(0.1, n.endTime - (currentTime - secondsPerBar)),
        })).filter(n => n.startTime >= 0 && n.endTime > n.startTime);

        const seed = {
            ticksPerQuarter: 220,
            totalTime: secondsPerBar,
            tempos: [{ time: 0, qpm: params.tempo }],
            timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
            notes: recentNotes.length > 0 ? recentNotes : [
                { pitch: 36, startTime: 0, endTime: 0.5, velocity: 100, isDrum: true, instrument: 0 },
                { pitch: 42, startTime: 0, endTime: 0.5, velocity: 80, isDrum: true, instrument: 0 },
            ],
            controlChanges: [],
        };

        const quantizedSeed = core.sequences.quantizeNoteSequence(seed, STEPS_PER_QUARTER);
        const barsToGen = Math.min(4, targetBars - barsGenerated);

        try {
            const continuation = await drumsRnn.continueSequence(
                quantizedSeed, barsToGen * stepsPerBar, params.temperature
            );
            for (const note of continuation.notes) {
                allNotes.push({
                    pitch: note.pitch,
                    startTime: note.startTime + currentTime,
                    endTime: note.endTime + currentTime,
                    velocity: note.velocity || 100,
                    program: 0, instrument: 0, isDrum: true,
                });
            }
        } catch (e) {
            console.error('Drums continuation error, looping:', e.message);
            for (const note of seedSeq.notes) {
                allNotes.push({ ...note, startTime: note.startTime + currentTime, endTime: note.endTime + currentTime });
            }
        }
        currentTime += barsToGen * secondsPerBar;
        barsGenerated += 4;
    }

    drumsRnn.dispose();
    return { ...seedSeq, notes: allNotes, totalTime: currentTime, controlChanges: [] };
}

function extendProgrammatic(seedSeq, targetDuration) {
    /**
     * Simple loop extension for bass/chords.
     * Loop the original pattern, shifting time offsets.
     */
    const allNotes = [...seedSeq.notes];
    const origDuration = seedSeq.totalTime;
    if (origDuration <= 0) return seedSeq;

    let t = origDuration;
    while (t < targetDuration) {
        for (const note of seedSeq.notes) {
            if (note.startTime + t >= targetDuration) break;
            allNotes.push({
                ...note,
                startTime: note.startTime + t,
                endTime: Math.min(note.endTime + t, targetDuration),
            });
        }
        t += origDuration;
    }
    return { ...seedSeq, notes: allNotes, totalTime: targetDuration, controlChanges: [] };
}

async function main() {
    const input = fs.readFileSync(0, 'utf-8');
    const params = JSON.parse(input);

    const scalePitches = buildScalePitches(params.root, params.scaleIntervals);
    const secondsPerBar = (60.0 / params.tempo) * 4;
    const targetBars = Math.ceil(params.targetDuration / secondsPerBar);

    console.error(`Extending to ${targetBars} bars (~${params.targetDuration}s) at ${params.tempo} BPM`);

    // Read original MIDIs
    const melodyMidi = readMidi(params.melodyMidi);
    const drumsMidi = readMidi(params.drumsMidi);
    const bassMidi = readMidi(params.bassMidi);
    const chordsMidi = readMidi(params.chordsMidi);

    // Convert to note sequences
    const melodySeed = midiToNoteSequence(melodyMidi);
    const drumsSeed = midiToNoteSequence(drumsMidi, true);
    const bassSeed = midiToNoteSequence(bassMidi);
    const chordsSeed = midiToNoteSequence(chordsMidi);

    // Extend each track
    const extendedMelody = await extendMelody(melodySeed, params, scalePitches, targetBars);
    const extendedDrums = await extendDrums(drumsSeed, params, targetBars);
    const extendedBass = extendProgrammatic(bassSeed, params.targetDuration);
    const extendedChords = extendProgrammatic(chordsSeed, params.targetDuration);

    // Write extended MIDIs
    const outputDir = params.outputDir;
    fs.mkdirSync(outputDir, { recursive: true });

    for (const [name, seq] of [
        ['melody.mid', extendedMelody],
        ['drums.mid', extendedDrums],
        ['bass.mid', extendedBass],
        ['chords.mid', extendedChords],
    ]) {
        const midiBytes = core.sequenceProtoToMidi(seq);
        fs.writeFileSync(path.join(outputDir, name), Buffer.from(midiBytes));
    }

    console.error('Extension complete');
    // Output summary as JSON to stdout
    console.log(JSON.stringify({
        melody_notes: extendedMelody.notes.length,
        drums_notes: extendedDrums.notes.length,
        bass_notes: extendedBass.notes.length,
        chords_notes: extendedChords.notes.length,
        target_duration: params.targetDuration,
        target_bars: targetBars,
    }));
}

main().catch(e => { console.error(e); process.exit(1); });
```

**Step 2: Write Python wrapper**

Write `hymnal-gargler/extender.py`:

```python
"""Python wrapper for Magenta.js MIDI extension."""
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the Node.js script
_SCRIPT = Path(__file__).parent / "extend_midi.js"


def extend_midi(
    melody_path: Path,
    drums_path: Path,
    bass_path: Path,
    chords_path: Path,
    output_dir: Path,
    target_duration: float = 40.0,
    scale: str = "Major",
    root: str = "C",
    scale_intervals: list[int] | None = None,
    tempo: int = 120,
    chords: list[str] | None = None,
    temperature: float = 1.0,
    melody_instrument: int = 0,
) -> dict:
    """Extend MIDI tracks using Magenta.js.

    Args:
        melody_path: Path to melody.mid
        drums_path: Path to drums.mid
        bass_path: Path to bass.mid
        chords_path: Path to chords.mid
        output_dir: Directory for extended MIDI files
        target_duration: Target duration in seconds
        scale: Scale name (for logging)
        root: Root note (e.g., "C", "F#")
        scale_intervals: Semitone intervals (default: major scale)
        tempo: BPM
        chords: Chord symbols for ImprovRNN
        temperature: Base temperature for Magenta models
        melody_instrument: MIDI program number

    Returns:
        Dict with note counts per track.
    """
    if scale_intervals is None:
        scale_intervals = [0, 2, 4, 5, 7, 9, 11]  # major
    if chords is None:
        chords = ["C", "G", "Am", "F"]

    output_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "melodyMidi": str(melody_path),
        "drumsMidi": str(drums_path),
        "bassMidi": str(bass_path),
        "chordsMidi": str(chords_path),
        "outputDir": str(output_dir),
        "targetDuration": target_duration,
        "scale": scale,
        "root": root,
        "scaleIntervals": scale_intervals,
        "tempo": tempo,
        "chords": chords,
        "temperature": temperature,
        "melodyInstrument": melody_instrument,
    }

    logger.info(f"Extending MIDI to ~{target_duration}s ({scale} in {root}, {tempo} BPM)")

    result = subprocess.run(
        ["node", str(_SCRIPT)],
        input=json.dumps(params),
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        logger.error(f"Magenta extension failed: {result.stderr}")
        # Fallback: copy originals
        logger.warning("Falling back to simple loop")
        return _fallback_loop(
            melody_path, drums_path, bass_path, chords_path, output_dir
        )

    try:
        summary = json.loads(result.stdout)
        logger.info(f"Extended: {summary}")
        return summary
    except json.JSONDecodeError:
        logger.warning(f"Could not parse Magenta output: {result.stdout}")
        return {}


def _fallback_loop(melody_path, drums_path, bass_path, chords_path, output_dir):
    """Copy originals as fallback (will be looped during synthesis)."""
    import shutil
    for src, name in [
        (melody_path, "melody.mid"),
        (drums_path, "drums.mid"),
        (bass_path, "bass.mid"),
        (chords_path, "chords.mid"),
    ]:
        shutil.copy2(src, output_dir / name)
    return {"fallback": True}
```

**Step 3: Write tests for the Python wrapper**

Write `hymnal-gargler/tests/test_extender.py`:

```python
"""Tests for MIDI extender (Python wrapper)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from extender import extend_midi, _fallback_loop


def test_fallback_loop_copies_files(tmp_path):
    """Fallback should copy original files to output dir."""
    # Create dummy MIDI files
    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        (tmp_path / name).write_bytes(b"MThd dummy")

    output = tmp_path / "output"
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
```

**Step 4: Run tests**

```bash
python -m pytest hymnal-gargler/tests/test_extender.py -v
```

Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/extend_midi.js hymnal-gargler/extender.py hymnal-gargler/tests/test_extender.py
git commit -m "feat(hymnal-gargler): add Magenta.js MIDI extension with Python wrapper"
```

---

### Task 6: Mixer

Synthesize extended MIDI tracks and mix with vocal.

**Files:**
- Create: `hymnal-gargler/mixer.py`
- Create: `hymnal-gargler/tests/test_mixer.py`

**Step 1: Write the failing test**

Write `hymnal-gargler/tests/test_mixer.py`:

```python
"""Tests for mixer."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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
    assert "ffmpeg" in cmd[0]
    assert "/tmp/vocal.wav" in " ".join(str(c) for c in cmd)
    assert "/tmp/midi.wav" in " ".join(str(c) for c in cmd)
    assert "amix" in " ".join(str(c) for c in cmd)
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest hymnal-gargler/tests/test_mixer.py -v
```

Expected: FAIL

**Step 3: Write implementation**

Write `hymnal-gargler/mixer.py`:

```python
"""Mix vocal track with MIDI backing tracks."""
import importlib.util
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE = Path(__file__).parent.parent


def _import_synthesizer():
    """Import synthesize_preview from midi-bot/src/synthesizer.py."""
    synth_path = _BASE / "midi-bot" / "src" / "synthesizer.py"
    spec = importlib.util.spec_from_file_location("midi_synthesizer", synth_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.synthesize_preview


def synthesize_midi_backing(midi_dir: Path, output_path: Path) -> bool:
    """Synthesize all 4 MIDI tracks into a single WAV.

    Args:
        midi_dir: Directory containing melody.mid, drums.mid, bass.mid, chords.mid
        output_path: Output WAV path

    Returns:
        True on success.
    """
    synthesize = _import_synthesizer()
    return synthesize(str(midi_dir), str(output_path))


def build_mix_command(
    vocal_path: Path,
    midi_wav_path: Path,
    output_path: Path,
    vocal_weight: float = 0.8,
    midi_weight: float = 0.5,
) -> list[str]:
    """Build ffmpeg command to mix vocal over MIDI backing.

    Returns:
        Command as list of strings.
    """
    return [
        "ffmpeg", "-y",
        "-i", str(midi_wav_path),
        "-i", str(vocal_path),
        "-filter_complex",
        f"[0]aresample=16000[m];[1]aresample=16000[v];"
        f"[m][v]amix=inputs=2:duration=longest:weights={midi_weight} {vocal_weight}[out]",
        "-map", "[out]",
        "-ar", "16000",
        str(output_path),
    ]


def mix_tracks(
    vocal_path: Path,
    midi_dir: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Produce the two output files: a cappella and full mix.

    Args:
        vocal_path: Path to a cappella WAV.
        midi_dir: Directory with extended MIDI files.
        output_dir: Output directory.

    Returns:
        Tuple of (full_mix_path, acappella_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    acappella_path = output_dir / "acappella.wav"
    full_mix_path = output_dir / "full_mix.wav"

    # Copy a cappella
    subprocess.run(["cp", str(vocal_path), str(acappella_path)], capture_output=True)

    # Synthesize MIDI backing
    midi_wav = output_dir / "midi_backing.wav"
    success = synthesize_midi_backing(midi_dir, midi_wav)

    if success and midi_wav.exists():
        # Mix vocal + MIDI
        cmd = build_mix_command(acappella_path, midi_wav, full_mix_path)
        subprocess.run(cmd, capture_output=True)
    else:
        logger.warning("MIDI synthesis failed, using a cappella as full mix")
        subprocess.run(["cp", str(acappella_path), str(full_mix_path)], capture_output=True)

    # Convert both to OGG
    for wav in [acappella_path, full_mix_path]:
        ogg = wav.with_suffix(".ogg")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(wav), "-b:a", "64k", str(ogg),
        ], capture_output=True)

    return full_mix_path, acappella_path
```

**Step 4: Run tests**

```bash
python -m pytest hymnal-gargler/tests/test_mixer.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/mixer.py hymnal-gargler/tests/test_mixer.py
git commit -m "feat(hymnal-gargler): add mixer for vocal + MIDI backing"
```

---

### Task 7: Slack Fetcher

Fetch most recent MIDI from #midieval and videos from #sample-sale.

**Files:**
- Create: `hymnal-gargler/slack_fetcher.py`
- Create: `hymnal-gargler/tests/test_slack_fetcher.py`

**Step 1: Write the failing test**

Write `hymnal-gargler/tests/test_slack_fetcher.py`:

```python
"""Tests for Slack fetcher."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from slack_fetcher import parse_midi_message


def test_parse_midi_message_valid():
    text = (
        ":musical_note: *Daily MIDI* — Hirajoshi in F# (145 BPM)\n"
        "_Bureaucrats dancing in the rain_\n\n"
        ":musical_keyboard: Melody — ImprovRNN, Koto (MIDI 107), temperature 1.2\n"
        ":drum_with_drumsticks: Drums — DrumsRNN, temperature 1.2\n"
        ":guitar: Bass — Programmatic\n"
        ":musical_score: Chords — F#m7 B7 E7 A7"
    )
    result = parse_midi_message(text)
    assert result is not None
    assert result["scale"] == "Hirajoshi"
    assert result["root"] == "F#"
    assert result["tempo"] == 145
    assert result["description"] == "Bureaucrats dancing in the rain"


def test_parse_midi_message_no_match():
    assert parse_midi_message("just a regular message") is None


def test_parse_midi_message_extracts_chords():
    text = "*Daily MIDI* — Blues in A (120 BPM)\n_test_\n:musical_score: Chords — Am Em G D"
    result = parse_midi_message(text)
    assert result["chords"] == ["Am", "Em", "G", "D"]
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest hymnal-gargler/tests/test_slack_fetcher.py -v
```

Expected: FAIL

**Step 3: Write implementation**

Write `hymnal-gargler/slack_fetcher.py`:

```python
"""Fetch MIDI files from #midieval and videos from #sample-sale."""
import importlib.util
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

_BASE = Path(__file__).parent.parent

MIDIEVAL_CHANNEL = "midieval"
SAMPLE_SALE_CHANNEL = "sample-sale"
MIDI_FILENAMES = {"melody.mid", "drums.mid", "bass.mid", "chords.mid"}


def parse_midi_message(text: str) -> dict | None:
    """Parse a Daily MIDI bot message into metadata.

    Returns None if the message doesn't match the expected format.
    """
    header = re.search(
        r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)', text
    )
    if not header:
        return None

    scale = header.group(1).strip()
    root = header.group(2)
    tempo = int(header.group(3))

    # Description (italic text)
    desc_match = re.search(r'_(.+?)_', text)
    description = desc_match.group(1) if desc_match else ""

    # Chords
    chords_match = re.search(r'Chords\s*—\s*(.+?)(?:\n|$)', text)
    chords = chords_match.group(1).split() if chords_match else []

    # Melody instrument
    inst_match = re.search(r'MIDI\s+(\d+)', text)
    melody_instrument = int(inst_match.group(1)) if inst_match else 0

    # Temperature
    temp_match = re.search(r'temperature\s+([\d.]+)', text)
    temperature = float(temp_match.group(1)) if temp_match else 1.0

    return {
        "scale": scale,
        "root": root,
        "tempo": tempo,
        "description": description,
        "chords": chords,
        "melody_instrument": melody_instrument,
        "temperature": temperature,
    }


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Find a Slack channel ID by name."""
    cursor = None
    while True:
        kwargs = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == channel_name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


def _download_with_auth(url: str, token: str, timeout: int = 30) -> bytes:
    """Download preserving auth header across redirects."""
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp.content
    raise requests.TooManyRedirects(f"Too many redirects for {url}")


def fetch_latest_midi(
    token: str,
    download_dir: Path,
) -> tuple[dict | None, str | None]:
    """Fetch the most recent Daily MIDI post and its 4 MIDI files.

    Returns:
        Tuple of (metadata dict, permalink) or (None, None) if not found.
    """
    client = WebClient(token=token)
    channel_id = find_channel_id(client, MIDIEVAL_CHANNEL)
    if not channel_id:
        logger.error(f"Channel #{MIDIEVAL_CHANNEL} not found")
        return None, None

    # Find most recent Daily MIDI message
    cursor = None
    metadata = None
    thread_ts = None

    while True:
        kwargs = {"channel": channel_id, "limit": 50}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)

        for msg in resp["messages"]:
            parsed = parse_midi_message(msg.get("text", ""))
            if parsed:
                thread_ts = msg["ts"]
                ts_dt = datetime.fromtimestamp(float(thread_ts), tz=timezone.utc)
                parsed["date"] = ts_dt.strftime("%Y-%m-%d")
                metadata = parsed
                break

        if metadata:
            break

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    if not metadata or not thread_ts:
        logger.error("No Daily MIDI messages found")
        return None, None

    # Build permalink
    permalink = f"https://slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}"

    # Download MIDI files from thread
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_replies(**kwargs)

        for msg in resp["messages"]:
            for f in msg.get("files", []):
                name = f.get("name", "")
                if name not in MIDI_FILENAMES:
                    continue
                url = f.get("url_private_download") or f.get("url_private")
                if not url:
                    continue
                try:
                    data = _download_with_auth(url, token)
                    if not data.startswith(b"MThd"):
                        logger.warning(f"Invalid MIDI: {name}")
                        continue
                    (download_dir / name).write_bytes(data)
                    downloaded.append(name)
                except Exception as e:
                    logger.error(f"Failed to download {name}: {e}")

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    logger.info(f"Downloaded {len(downloaded)} MIDI files: {downloaded}")
    return metadata, permalink


def fetch_videos(
    token: str,
    download_dir: Path,
    max_videos: int = 5,
    channel: str = SAMPLE_SALE_CHANNEL,
) -> list[dict]:
    """Fetch random videos from #sample-sale using glottisdale's fetch module.

    Returns:
        List of dicts with 'path' and 'permalink'.
    """
    fetch_mod_path = _BASE / "glottisdale" / "slack" / "glottisdale_slack" / "fetch.py"
    spec = importlib.util.spec_from_file_location("glottisdale_fetch", fetch_mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    return mod.fetch_videos(
        token=token,
        channel=f"#{channel}",
        max_videos=max_videos,
        download_dir=download_dir,
    )
```

**Step 4: Run tests**

```bash
python -m pytest hymnal-gargler/tests/test_slack_fetcher.py -v
```

Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/slack_fetcher.py hymnal-gargler/tests/test_slack_fetcher.py
git commit -m "feat(hymnal-gargler): add Slack fetcher for MIDI and videos"
```

---

### Task 8: Slack Poster

Post results to #glottisdale with link back to #midieval.

**Files:**
- Create: `hymnal-gargler/slack_poster.py`
- Create: `hymnal-gargler/tests/test_slack_poster.py`

**Step 1: Write the failing test**

Write `hymnal-gargler/tests/test_slack_poster.py`:

```python
"""Tests for Slack poster."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from slack_poster import format_message


def test_format_message():
    msg = format_message(
        scale="Hirajoshi",
        root="F#",
        tempo=145,
        description="Bureaucrats dancing in the rain",
        source_link="https://slack.com/archives/C123/p456",
    )
    assert "Hymnal Gargler" in msg
    assert "Hirajoshi" in msg
    assert "F#" in msg
    assert "145 BPM" in msg
    assert "Bureaucrats dancing in the rain" in msg
    assert "https://slack.com/archives/C123/p456" in msg


def test_format_message_no_description():
    msg = format_message("Blues", "A", 120, "", "https://link")
    assert "Hymnal Gargler" in msg
    assert "_" not in msg or "Blues" in msg  # no empty italics
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest hymnal-gargler/tests/test_slack_poster.py -v
```

Expected: FAIL

**Step 3: Write implementation**

Write `hymnal-gargler/slack_poster.py`:

```python
"""Post Hymnal Gargler results to Slack."""
import logging
import time
from pathlib import Path

from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def format_message(
    scale: str,
    root: str,
    tempo: int,
    description: str,
    source_link: str,
) -> str:
    """Format the Slack message for posting."""
    lines = [
        f":microphone: *Hymnal Gargler* — {scale} in {root} ({tempo} BPM)",
    ]
    if description:
        lines.append(f"_{description}_")
    lines.append("")
    lines.append(f"Source: <{source_link}|#midieval>")
    return "\n".join(lines)


def post_results(
    token: str,
    channel: str,
    full_mix_path: Path,
    acappella_path: Path,
    metadata: dict,
    source_link: str,
) -> None:
    """Post the two audio tracks to Slack.

    Args:
        token: Slack bot token.
        channel: Channel name (e.g., "glottisdale").
        full_mix_path: Path to full mix OGG.
        acappella_path: Path to a cappella OGG.
        metadata: Dict with scale, root, tempo, description.
        source_link: Permalink to the source #midieval post.
    """
    client = WebClient(token=token)

    # Resolve channel ID
    from slack_fetcher import find_channel_id
    channel_name = channel.lstrip("#")
    channel_id = find_channel_id(client, channel_name)
    if not channel_id:
        raise ValueError(f"Channel #{channel_name} not found")

    message = format_message(
        scale=metadata["scale"],
        root=metadata["root"],
        tempo=metadata["tempo"],
        description=metadata.get("description", ""),
        source_link=source_link,
    )

    # Upload full mix as main message
    full_mix_ogg = full_mix_path.with_suffix(".ogg")
    if not full_mix_ogg.exists():
        full_mix_ogg = full_mix_path  # fall back to WAV

    resp = _upload_with_retry(
        client,
        channels=channel_id,
        file=str(full_mix_ogg),
        filename="hymnal_gargler_mix.ogg",
        initial_comment=message,
        title="Hymnal Gargler — Full Mix",
    )

    # Get thread_ts for reply
    thread_ts = _get_thread_ts(client, resp)

    if thread_ts:
        # Upload a cappella as reply
        acappella_ogg = acappella_path.with_suffix(".ogg")
        if not acappella_ogg.exists():
            acappella_ogg = acappella_path

        try:
            _upload_with_retry(
                client,
                channels=channel_id,
                file=str(acappella_ogg),
                filename="hymnal_gargler_acappella.ogg",
                initial_comment=":speaking_head_in_silhouette: A cappella (vocal only)",
                title="Hymnal Gargler — A Cappella",
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.warning(f"Failed to upload a cappella: {e}")

    logger.info(f"Posted to #{channel_name}")


def _upload_with_retry(client: WebClient, max_retries: int = 3, **kwargs) -> dict:
    """Upload file with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return client.files_upload_v2(**kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning(f"Upload failed (attempt {attempt + 1}), retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise


def _get_thread_ts(client: WebClient, upload_resp: dict) -> str | None:
    """Extract thread_ts from upload response."""
    try:
        file_obj = upload_resp.get("file", {})
        file_id = file_obj.get("id")
        if not file_id:
            return None
        info = client.files_info(file=file_id)
        shares = info.get("file", {}).get("shares", {})
        for channel_shares in shares.get("public", {}).values():
            if channel_shares:
                return channel_shares[0].get("ts")
        for channel_shares in shares.get("private", {}).values():
            if channel_shares:
                return channel_shares[0].get("ts")
    except Exception as e:
        logger.warning(f"Could not get thread_ts: {e}")
    return None
```

**Step 4: Run tests**

```bash
python -m pytest hymnal-gargler/tests/test_slack_poster.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add hymnal-gargler/slack_poster.py hymnal-gargler/tests/test_slack_poster.py
git commit -m "feat(hymnal-gargler): add Slack poster"
```

---

### Task 9: CLI Entry Point

Argparse CLI supporting local mode and Slack mode.

**Files:**
- Create: `hymnal-gargler/cli.py`

**Step 1: Write CLI**

Write `hymnal-gargler/cli.py`:

```python
"""Hymnal Gargler CLI — pitch-mapped vocal collages over MIDI melodies."""
import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("hymnal-gargler")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Hymnal Gargler: pitch-map nonsense syllables to MIDI melodies"
    )

    # Input sources
    parser.add_argument(
        "--midi", nargs=4, metavar=("MELODY", "DRUMS", "BASS", "CHORDS"),
        help="Local MIDI files (melody drums bass chords)",
    )
    parser.add_argument(
        "--audio", nargs="+", metavar="FILE",
        help="Local audio/video files for syllable source",
    )

    # Output
    parser.add_argument(
        "--output-dir", default="./hymnal-gargler-output",
        help="Output directory (default: ./hymnal-gargler-output)",
    )

    # Processing
    parser.add_argument("--target-duration", type=float, default=40.0,
                        help="Target output duration in seconds (default: 40)")
    parser.add_argument("--max-videos", type=int, default=5,
                        help="Number of videos to fetch from #sample-sale (default: 5)")
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")

    # Vocal mapping
    parser.add_argument("--drift-range", type=float, default=2.0,
                        help="Max semitones of melodic drift (default: 2)")
    parser.add_argument("--vibrato", action=argparse.BooleanOptionalAction, default=True,
                        help="Enable vibrato on sustained notes")
    parser.add_argument("--chorus", action=argparse.BooleanOptionalAction, default=True,
                        help="Enable chorus layering")

    # Slack
    parser.add_argument("--source-channel", default="sample-sale",
                        help="Slack channel for audio source (default: sample-sale)")
    parser.add_argument("--dest-channel", default="glottisdale",
                        help="Slack channel to post to (default: glottisdale)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Process but don't post to Slack")
    parser.add_argument("--no-post", action="store_true",
                        help="Local output only, skip Slack entirely")

    # Logging
    parser.add_argument("-v", "--verbose", action="store_true")

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    token = os.environ.get("SLACK_BOT_TOKEN")
    local_mode = args.midi is not None and args.audio is not None

    if not local_mode and not token:
        logger.error("Either provide --midi + --audio for local mode, or set SLACK_BOT_TOKEN")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="hymnal-gargler-") as tmpdir:
        work_dir = Path(tmpdir)

        # === Step 1: Get MIDI files ===
        if args.midi:
            midi_paths = [Path(p) for p in args.midi]
            midi_dir = work_dir / "midi"
            midi_dir.mkdir()
            import shutil
            for p in midi_paths:
                shutil.copy2(p, midi_dir / p.name)
            metadata = {"scale": "Unknown", "root": "C", "tempo": 120,
                        "description": "", "chords": ["C"], "melody_instrument": 0,
                        "temperature": 1.0}
            source_link = ""
        else:
            from slack_fetcher import fetch_latest_midi
            midi_dir = work_dir / "midi"
            metadata, source_link = fetch_latest_midi(token, midi_dir)
            if not metadata:
                logger.error("No MIDI found in #midieval")
                sys.exit(1)

        logger.info(f"MIDI: {metadata['scale']} in {metadata['root']} ({metadata['tempo']} BPM)")

        # === Step 2: Get audio sources ===
        if args.audio:
            audio_paths = [Path(p) for p in args.audio]
        else:
            from slack_fetcher import fetch_videos
            video_dir = work_dir / "videos"
            video_dir.mkdir()
            sources = fetch_videos(token, video_dir, args.max_videos, args.source_channel)
            audio_paths = [s["path"] for s in sources]
            if not audio_paths:
                logger.error("No videos found in #sample-sale")
                sys.exit(1)

        logger.info(f"Audio sources: {len(audio_paths)} files")

        # === Step 3: Prepare syllables ===
        from syllable_prep import prepare_syllables
        syllables = prepare_syllables(
            audio_paths, work_dir,
            whisper_model=args.whisper_model,
            max_semitone_shift=5.0,
        )
        logger.info(f"Prepared {len(syllables)} normalized syllables")

        # Compute median F0 of pool
        from statistics import median
        voiced_f0 = [s.f0 for s in syllables if s.f0 and s.f0 > 0]
        median_f0 = median(voiced_f0) if voiced_f0 else 200.0

        # === Step 4: Extend MIDI ===
        from extender import extend_midi
        from midi_parser import parse_midi

        # Load scale intervals from midi-bot's scales.json
        import json
        scales_path = Path(__file__).parent.parent / "midi-bot" / "scales.json"
        scale_intervals = [0, 2, 4, 5, 7, 9, 11]  # default major
        if scales_path.exists():
            with open(scales_path) as f:
                scales_db = json.load(f)
            if metadata["scale"] in scales_db:
                scale_intervals = scales_db[metadata["scale"]]

        extended_dir = work_dir / "extended"
        extend_midi(
            melody_path=midi_dir / "melody.mid",
            drums_path=midi_dir / "drums.mid",
            bass_path=midi_dir / "bass.mid",
            chords_path=midi_dir / "chords.mid",
            output_dir=extended_dir,
            target_duration=args.target_duration,
            scale=metadata["scale"],
            root=metadata["root"],
            scale_intervals=scale_intervals,
            tempo=metadata["tempo"],
            chords=metadata.get("chords", ["C"]),
            temperature=metadata.get("temperature", 1.0),
            melody_instrument=metadata.get("melody_instrument", 0),
        )

        # === Step 5: Map vocals to melody ===
        from vocal_mapper import plan_note_mapping, render_vocal_track

        extended_melody = parse_midi(extended_dir / "melody.mid")
        mappings = plan_note_mapping(
            extended_melody.notes,
            pool_size=len(syllables),
            seed=args.seed,
            drift_range=args.drift_range,
            chorus_probability=0.3 if args.chorus else 0.0,
        )

        # Disable vibrato/chorus if flags are off
        if not args.vibrato:
            for m in mappings:
                m.apply_vibrato = False
        if not args.chorus:
            for m in mappings:
                m.apply_chorus = False

        vocal_path = render_vocal_track(
            mappings, syllables, work_dir, median_f0,
            target_duration=args.target_duration,
        )
        logger.info(f"Vocal track: {vocal_path}")

        # === Step 6: Mix ===
        from mixer import mix_tracks
        full_mix, acappella = mix_tracks(vocal_path, extended_dir, output_dir)
        logger.info(f"Output: {full_mix}, {acappella}")

        # === Step 7: Post to Slack ===
        if not args.no_post and not local_mode:
            if args.dry_run:
                logger.info("Dry run — skipping Slack post")
            else:
                from slack_poster import post_results
                post_results(
                    token=token,
                    channel=args.dest_channel,
                    full_mix_path=full_mix,
                    acappella_path=acappella,
                    metadata=metadata,
                    source_link=source_link or "",
                )

    logger.info("Done!")


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add hymnal-gargler/cli.py
git commit -m "feat(hymnal-gargler): add CLI entry point"
```

---

### Task 10: Bot Orchestrator (GitHub Actions Entry Point)

**Files:**
- Create: `hymnal-gargler/bot.py`

**Step 1: Write bot.py**

Write `hymnal-gargler/bot.py`:

```python
#!/usr/bin/env python3
"""Hymnal Gargler bot — GitHub Actions entry point."""
import sys
from pathlib import Path

# Add hymnal-gargler directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cli import main

if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add hymnal-gargler/bot.py
git commit -m "feat(hymnal-gargler): add bot.py entry point"
```

---

### Task 11: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/hymnal-gargler.yml`

**Step 1: Write workflow**

Write `.github/workflows/hymnal-gargler.yml`:

```yaml
name: Hymnal Gargler

on:
  schedule:
    - cron: '0 18 * * *'  # 6pm UTC / 11am PT daily
  workflow_dispatch:

jobs:
  gargle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Set up Node 18
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg librubberband-dev

      - name: Install Python dependencies
        run: |
          pip install -r hymnal-gargler/requirements.txt
          pip install openai-whisper g2p_en
          python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng')"

      - name: Install Node dependencies
        working-directory: hymnal-gargler
        run: npm install

      - name: Cache Whisper model
        uses: actions/cache@v4
        with:
          path: ~/.cache/whisper
          key: whisper-base

      - name: Run Hymnal Gargler
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        working-directory: hymnal-gargler
        run: python bot.py --output-dir ../hymnal-gargler-output --verbose

      - name: Commit output (if any)
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if [ -d hymnal-gargler-output ]; then
            git add hymnal-gargler-output/ || true
            git diff --cached --quiet || git commit -m "chore: hymnal gargler output $(date +%Y-%m-%d)"
            git push
          fi
```

**Step 2: Commit**

```bash
git add .github/workflows/hymnal-gargler.yml
git commit -m "feat(hymnal-gargler): add GitHub Actions workflow"
```

---

### Task 12: Integration Test with Local Files

Run the full pipeline locally with existing puke-box MIDI files and glottisdale test clips.

**Files:**
- Create: `hymnal-gargler/tests/test_integration.py`

**Step 1: Write integration test**

Write `hymnal-gargler/tests/test_integration.py`:

```python
"""Integration test — run full pipeline with local files."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO_ROOT = Path(__file__).parent.parent.parent
PUKE_BOX = REPO_ROOT / "puke-box"


def test_cli_local_mode_help():
    """CLI should show help without error."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "--help"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "Hymnal Gargler" in result.stdout


def test_cli_requires_input():
    """CLI should error without --midi or SLACK_BOT_TOKEN."""
    result = subprocess.run(
        [sys.executable, "-m", "cli", "--no-post"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
        env={**__import__("os").environ, "SLACK_BOT_TOKEN": ""},
    )
    assert result.returncode != 0
```

**Step 2: Run integration test**

```bash
python -m pytest hymnal-gargler/tests/test_integration.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add hymnal-gargler/tests/test_integration.py
git commit -m "test(hymnal-gargler): add integration tests"
```

---

### Task 13: End-to-End Local Test

Actually run the pipeline with real MIDI files and the test audio clips.

**Step 1: Run locally**

```bash
cd /Users/jake/au-supply/ausupply.github.io

# Unzip glottisdale clips as audio source
mkdir -p /tmp/hg-test-audio
unzip -o glottisdale-2026-02-15-clips.zip -d /tmp/hg-test-audio/

# Run with local MIDI + audio
python hymnal-gargler/cli.py \
    --midi puke-box/2026-02-14-161653/melody.mid \
          puke-box/2026-02-14-161653/drums.mid \
          puke-box/2026-02-14-161653/bass.mid \
          puke-box/2026-02-14-161653/chords.mid \
    --audio /tmp/hg-test-audio/*.wav \
    --output-dir /tmp/hg-test-output \
    --target-duration 20 \
    --no-post \
    --verbose
```

**Step 2: Verify output**

Check that `/tmp/hg-test-output/` contains:
- `full_mix.wav` and `full_mix.ogg`
- `acappella.wav` and `acappella.ogg`

Play and listen for:
- Syllables pitched to the melody
- Vibrato on held notes
- Chorus layering on sustained notes
- Smooth transitions (no harsh clicks)

**Step 3: Iterate on vocal quality**

Adjust parameters as needed. Common tweaks:
- `--drift-range 1` for tighter melody following
- `--no-chorus` to hear the base voice clearly
- Crossfade values in vocal_mapper.py
- Vibrato depth/rate in vocal_mapper.py

---

### Task 14: Documentation & Memory Update

**Step 1: Update MEMORY.md**

Add Hymnal Gargler section to `/Users/jake/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md`.

**Step 2: Final commit**

```bash
git add -A
git commit -m "docs: update memory with Hymnal Gargler"
```

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
            n_syls = rng.choice([1, 1, 1, 2, 2, 3])
        else:
            n_syls = rng.choice([1, 2, 2, 3, 3, 4])

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

        # Time stretch ratio: placeholder, computed at render time
        time_ratio = 1.0

        mappings.append(NoteMapping(
            note_pitch=note.pitch,
            note_start=note.start,
            note_end=note.end,
            note_duration=duration,
            syllable_indices=indices,
            pitch_shift_semitones=drift,
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
    """Render a single note mapping to a WAV file."""
    note_dir = work_dir / f"note_{note_index:04d}"
    note_dir.mkdir(exist_ok=True)

    target_duration = mapping.note_duration
    n_syls = len(mapping.syllable_indices)
    per_syl_duration = target_duration / n_syls

    # Add rhythmic variation: +/-20% of exact duration
    rng = random.Random(note_index)
    syl_durations = []
    remaining = target_duration
    for i in range(n_syls):
        if i == n_syls - 1:
            syl_durations.append(remaining)
        else:
            variation = rng.uniform(0.8, 1.2)
            d = per_syl_duration * variation
            d = min(d, remaining - 0.05 * (n_syls - i - 1))
            d = max(d, 0.05)
            syl_durations.append(d)
            remaining -= d

    rendered_parts = []
    for i, (syl_idx, syl_dur) in enumerate(zip(mapping.syllable_indices, syl_durations)):
        syl = syllable_clips[syl_idx]

        # Compute total pitch shift: base (median->note) + drift
        base_shift = compute_target_pitch(mapping.note_pitch, median_f0, mapping.pitch_shift_semitones)
        shift = max(-max_shift, min(max_shift, base_shift))

        # Time stretch: syllable duration -> target per-syllable duration
        time_ratio = syl.duration / syl_dur if syl_dur > 0 else 1.0
        time_ratio = max(0.25, min(4.0, time_ratio))

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
    """Render all mappings into a complete vocal track."""
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
    parts_with_gaps = []
    for idx, (mapping, wav_path) in enumerate(rendered_notes):
        if idx > 0:
            prev_mapping = rendered_notes[idx - 1][0]
            gap_duration = mapping.note_start - prev_mapping.note_end
            if gap_duration > 0.01:
                gap_path = render_dir / f"gap_{idx:04d}.wav"
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"anullsrc=r=16000:cl=mono",
                    "-t", str(gap_duration),
                    "-ar", "16000", str(gap_path),
                ], capture_output=True)
                if gap_path.exists():
                    parts_with_gaps.append(gap_path)

        parts_with_gaps.append(wav_path)

    # Concatenate everything with crossfade
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
    """Apply vibrato via ffmpeg vibrato filter."""
    depth = min(depth_cents / 100.0, 1.0)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter:a", f"vibrato=f={rate_hz}:d={depth:.3f}",
        "-ar", "16000", str(output_path),
    ], capture_output=True)


def _apply_chorus(input_path: Path, output_path: Path, n_voices: int = 2):
    """Layer detuned copies for chorus effect."""
    rng = random.Random()
    voices = [input_path]  # original
    work_dir = output_path.parent

    for v in range(n_voices):
        detune_cents = rng.uniform(10, 15) * rng.choice([-1, 1])
        detune_ratio = 2 ** (detune_cents / 1200.0)
        delay_ms = rng.uniform(15, 30)

        voice_path = work_dir / f"chorus_voice_{v}.wav"
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

    # Mix all voices
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
    current = clip_paths[0]
    for i in range(1, len(clip_paths)):
        out = output_path.parent / f"_concat_temp_{i}.wav"

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

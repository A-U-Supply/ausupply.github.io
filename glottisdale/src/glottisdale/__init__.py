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
    """Run the full glottisdale pipeline."""
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

            # Extract audio (resample to 16kHz)
            audio_path = tmpdir / f"{source_name}.wav"
            extract_audio(input_path, audio_path)

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
            # Find which source file this syllable came from
            clip_source = "unknown"
            for src_name, src_syls in all_syllables.items():
                if group[0] in src_syls:
                    clip_source = src_name
                    break

            clip_idx = len(clips) + 1
            w_idx = group[0].word_index
            s_idx = 0
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

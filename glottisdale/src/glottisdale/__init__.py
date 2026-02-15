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


def _parse_range(s: str) -> tuple[int, int]:
    """Parse range string like '1-5' or '3' into (min, max)."""
    if "-" in s:
        parts = s.split("-", 1)
        return int(parts[0]), int(parts[1])
    val = int(s)
    return val, val


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
    syllables_per_clip: str = "1-5",
    target_duration: float = 10.0,
    crossfade_ms: float = 10,
    padding_ms: float = 25,
    gap: str = "200-500",
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
    spc_min, spc_max = _parse_range(syllables_per_clip)
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

        # Helper to find which source a syllable came from
        def _find_source(syl: Syllable) -> str:
            for src_name, src_syls in all_syllables.items():
                if syl in src_syls:
                    return src_name
            return "unknown"

        # Group syllables into variable-length nonsense "words"
        words: list[list[Syllable]] = []
        i = 0
        while i < len(selected):
            word_len = rng.randint(spc_min, spc_max)
            word = selected[i:i + word_len]
            if word:
                words.append(word)
            i += word_len

        # Build each word: cut individual syllables, fuse them tightly
        clips = []
        for word_idx, word_syls in enumerate(words):
            # Cut each syllable from its source audio
            syl_clip_paths = []
            for syl_idx, syl in enumerate(word_syls):
                syl_source = _find_source(syl)
                source_audio = tmpdir / f"{syl_source}.wav"
                syl_clip_path = tmpdir / f"word{word_idx:03d}_syl{syl_idx:02d}.wav"
                if source_audio.exists():
                    cut_clip(
                        input_path=source_audio,
                        output_path=syl_clip_path,
                        start=syl.start,
                        end=syl.end,
                        padding_ms=padding_ms,
                        fade_ms=0,
                    )
                    syl_clip_paths.append(syl_clip_path)

            if not syl_clip_paths:
                continue

            # Fuse syllables tightly into one "word" clip
            word_filename = f"{word_idx + 1:03d}_word.wav"
            word_output = clips_dir / word_filename
            if len(syl_clip_paths) == 1:
                shutil.copy2(syl_clip_paths[0], word_output)
            else:
                concatenate_clips(
                    syl_clip_paths, word_output,
                    crossfade_ms=crossfade_ms,
                )

            # Track dominant source for metadata
            word_sources = [_find_source(s) for s in word_syls]
            dominant = max(set(word_sources), key=word_sources.count)

            clips.append(Clip(
                syllables=word_syls,
                start=min(s.start for s in word_syls),
                end=max(s.end for s in word_syls),
                source=dominant,
                output_path=word_output,
            ))

        # Concatenate words with silence gaps between them
        gap_durations = []
        if len(clips) > 1:
            for _ in range(len(clips) - 1):
                gap_durations.append(rng.uniform(gap_min, gap_max))

        concatenated_path = output_dir / "concatenated.wav"
        clip_paths = [c.output_path for c in clips if c.output_path.exists()]
        if clip_paths:
            concatenate_clips(
                clip_paths,
                concatenated_path,
                crossfade_ms=0,
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

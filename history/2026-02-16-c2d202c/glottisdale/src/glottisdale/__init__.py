"""Glottisdale — syllable-level audio collage tool."""

import json
import logging
import random
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from glottisdale.align import get_aligner
from glottisdale.analysis import (
    read_wav,
    write_wav,
    compute_rms,
    estimate_f0,
    find_room_tone,
    find_breaths,
    generate_pink_noise,
)
from glottisdale.audio import (
    cut_clip,
    concatenate_clips,
    detect_input_type,
    extract_audio,
    get_duration,
    generate_silence,
    pitch_shift_clip,
    adjust_volume,
    mix_audio,
)
from glottisdale.phonotactics import order_syllables
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


# Default weights for syllables-per-word: favors 2-syllable words
_WORD_LENGTH_WEIGHTS = [0.30, 0.35, 0.25, 0.10]


def _weighted_word_length(min_syl: int, max_syl: int, rng: random.Random) -> int:
    """Pick a word length using weighted distribution.

    Weights skew toward 2-syllable words for natural-sounding output.
    Falls back to uniform if range doesn't match weight table.
    """
    choices = list(range(min_syl, max_syl + 1))
    if len(choices) == len(_WORD_LENGTH_WEIGHTS):
        return rng.choices(choices, weights=_WORD_LENGTH_WEIGHTS, k=1)[0]
    # Fallback: use truncated/padded weights or uniform
    if len(choices) <= len(_WORD_LENGTH_WEIGHTS):
        weights = _WORD_LENGTH_WEIGHTS[:len(choices)]
        return rng.choices(choices, weights=weights, k=1)[0]
    return rng.randint(min_syl, max_syl)


def _group_into_words(
    syllables: list[Syllable],
    spc_min: int,
    spc_max: int,
    rng: random.Random,
) -> list[list[Syllable]]:
    """Group syllables into variable-length words with phonotactic ordering."""
    words: list[list[Syllable]] = []
    i = 0
    while i < len(syllables):
        word_len = _weighted_word_length(spc_min, spc_max, rng)
        word = syllables[i:i + word_len]
        if word:
            if len(word) > 1:
                word = order_syllables(word, seed=rng.randint(0, 2**31))
            words.append(word)
        i += word_len
    return words


def _group_into_phrases(
    words: list[list[Syllable]],
    wpp_min: int,
    wpp_max: int,
    rng: random.Random,
) -> list[list[list[Syllable]]]:
    """Group words into phrases of variable length."""
    phrases: list[list[list[Syllable]]] = []
    i = 0
    while i < len(words):
        phrase_len = rng.randint(wpp_min, wpp_max)
        phrase = words[i:i + phrase_len]
        if phrase:
            phrases.append(phrase)
        i += phrase_len
    return phrases


def _group_into_sentences(
    phrases: list,
    pps_min: int,
    pps_max: int,
    rng: random.Random,
) -> list[list]:
    """Group phrases into sentence-level groups."""
    sentences: list[list] = []
    i = 0
    while i < len(phrases):
        sent_len = rng.randint(pps_min, pps_max)
        sentence = phrases[i:i + sent_len]
        if sentence:
            sentences.append(sentence)
        i += sent_len
    return sentences


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
    crossfade_ms: float = 30,
    padding_ms: float = 25,
    gap: str | None = None,
    words_per_phrase: str = "3-5",
    phrases_per_sentence: str = "2-3",
    phrase_pause: str = "400-700",
    sentence_pause: str = "800-1200",
    word_crossfade_ms: float = 50,
    aligner: str = "default",
    whisper_model: str = "base",
    seed: int | None = None,
    # Audio polish params
    noise_level_db: float = -40,
    room_tone: bool = True,
    pitch_normalize: bool = True,
    pitch_range: float = 5,
    breaths: bool = True,
    breath_probability: float = 0.6,
    volume_normalize: bool = True,
    prosodic_dynamics: bool = True,
) -> Result:
    """Run the full glottisdale pipeline."""
    rng = random.Random(seed)
    output_dir = Path(output_dir)
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Backward compat: if gap is provided, use it as phrase_pause
    if gap is not None:
        phrase_pause = gap
        gap_min, gap_max = _parse_gap(gap)
        sentence_pause = f"{gap_min * 2}-{gap_max * 2}"

    spc_min, spc_max = _parse_range(syllables_per_clip)
    wpp_min, wpp_max = _parse_range(words_per_phrase)
    pps_min, pps_max = _parse_range(phrases_per_sentence)
    pp_min, pp_max = _parse_gap(phrase_pause)
    sp_min, sp_max = _parse_gap(sentence_pause)
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

        # === Audio polish: analyze sources ===
        logger = logging.getLogger("glottisdale")
        source_room_tones: dict[str, Path] = {}  # source_name -> room tone WAV path
        source_breaths: dict[str, list[Path]] = {}  # source_name -> list of breath WAV paths

        for source_name in all_syllables:
            audio_path = tmpdir / f"{source_name}.wav"
            if not audio_path.exists():
                continue
            try:
                samples, sr = read_wav(audio_path)
            except Exception:
                continue

            # Extract room tone
            if room_tone:
                try:
                    rt = find_room_tone(samples, sr)
                    if rt is not None:
                        rt_start, rt_end = rt
                        rt_path = tmpdir / f"{source_name}_roomtone.wav"
                        rt_samples = samples[int(rt_start * sr):int(rt_end * sr)]
                        write_wav(rt_path, rt_samples, sr)
                        source_room_tones[source_name] = rt_path
                        logger.info(
                            f"Room tone found in {source_name}: "
                            f"{rt_start:.1f}-{rt_end:.1f}s"
                        )
                except Exception:
                    pass

            # Detect breaths
            if breaths:
                try:
                    # Build word-level boundaries from syllables
                    word_bounds: list[tuple[float, float]] = []
                    seen_words: set[tuple[str, int]] = set()
                    for syl in all_syllables[source_name]:
                        key = (syl.word, syl.word_index)
                        if key not in seen_words:
                            word_syls = [
                                s for s in all_syllables[source_name]
                                if s.word == syl.word
                                and s.word_index == syl.word_index
                            ]
                            word_bounds.append((
                                min(s.start for s in word_syls),
                                max(s.end for s in word_syls),
                            ))
                            seen_words.add(key)
                    word_bounds.sort()
                    detected = find_breaths(samples, sr, word_bounds)
                    if detected:
                        breath_paths = []
                        for bi, (bs, be) in enumerate(detected):
                            bp = tmpdir / f"{source_name}_breath_{bi:03d}.wav"
                            b_samples = samples[int(bs * sr):int(be * sr)]
                            write_wav(bp, b_samples, sr)
                            breath_paths.append(bp)
                        source_breaths[source_name] = breath_paths
                        logger.info(
                            f"Found {len(detected)} breaths in {source_name}"
                        )
                except Exception:
                    pass

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

        # Group syllables into phonotactically-ordered nonsense "words"
        words = _group_into_words(selected, spc_min, spc_max, rng)

        # Build each word: cut individual syllables, optionally normalize, fuse
        clips = []
        word_clip_paths = []

        # First pass: cut all syllable clips
        all_syl_clip_info = []  # (word_idx, syl_idx, syl_clip_path, syl)
        for word_idx, word_syls in enumerate(words):
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
                    all_syl_clip_info.append(
                        (word_idx, syl_idx, syl_clip_path, syl)
                    )

        # Pitch normalization: measure all F0s, shift to median
        if pitch_normalize and all_syl_clip_info:
            try:
                import numpy as np
                import math

                f0_values = []
                clip_f0s = {}
                for word_idx, syl_idx, clip_path, syl in all_syl_clip_info:
                    if clip_path.exists():
                        samples, sr = read_wav(clip_path)
                        f0 = estimate_f0(samples, sr)
                        if f0 is not None:
                            f0_values.append(f0)
                            clip_f0s[(word_idx, syl_idx)] = f0

                if f0_values:
                    target_f0 = float(np.median(f0_values))
                    logger.info(
                        f"Pitch normalization: target F0 = {target_f0:.1f}Hz "
                        f"(from {len(f0_values)} voiced clips)"
                    )
                    for word_idx, syl_idx, clip_path, syl in all_syl_clip_info:
                        f0 = clip_f0s.get((word_idx, syl_idx))
                        if f0 is not None and clip_path.exists():
                            semitones_shift = 12 * math.log2(target_f0 / f0)
                            # Clamp to pitch_range
                            semitones_shift = max(
                                -pitch_range,
                                min(pitch_range, semitones_shift),
                            )
                            if abs(semitones_shift) >= 0.1:
                                shifted = tmpdir / f"pitched_{clip_path.name}"
                                pitch_shift_clip(
                                    clip_path, shifted, semitones_shift
                                )
                                shutil.move(shifted, clip_path)
            except Exception:
                logger.debug("Pitch normalization failed, skipping")

        # Volume normalization: normalize RMS across all syllable clips
        if volume_normalize and all_syl_clip_info:
            try:
                import numpy as np
                import math

                rms_values = []
                for word_idx, syl_idx, clip_path, syl in all_syl_clip_info:
                    if clip_path.exists():
                        samples, sr = read_wav(clip_path)
                        rms_values.append(compute_rms(samples))

                if rms_values:
                    target_rms = float(np.median(rms_values))
                    if target_rms > 1e-6:
                        for (word_idx, syl_idx, clip_path,
                             syl) in all_syl_clip_info:
                            if clip_path.exists():
                                samples, sr = read_wav(clip_path)
                                clip_rms = compute_rms(samples)
                                if clip_rms > 1e-6:
                                    db_adjust = 20 * math.log10(
                                        target_rms / clip_rms
                                    )
                                    db_adjust = max(-20, min(20, db_adjust))
                                    if abs(db_adjust) >= 0.5:
                                        adjusted = (
                                            tmpdir / f"vol_{clip_path.name}"
                                        )
                                        adjust_volume(
                                            clip_path, adjusted, db_adjust
                                        )
                                        shutil.move(adjusted, clip_path)
            except Exception:
                logger.debug("Volume normalization failed, skipping")

        # Second pass: fuse syllables into words
        for word_idx, word_syls in enumerate(words):
            syl_clip_paths = [
                info[2] for info in all_syl_clip_info
                if info[0] == word_idx and info[2].exists()
            ]

            if not syl_clip_paths:
                word_clip_paths.append(None)
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
            word_clip_paths.append(word_output)

        # Filter to valid word clip paths
        valid_word_paths = [p for p in word_clip_paths if p is not None]

        # Group words into phrases, phrases into sentences
        phrases = _group_into_phrases(
            [[p] for p in valid_word_paths], wpp_min, wpp_max, rng
        )

        # Build phrase WAVs (words concatenated with crossfade, no gaps)
        phrase_paths = []
        for phrase_idx, phrase_word_groups in enumerate(phrases):
            phrase_clip_paths = [
                p for group in phrase_word_groups for p in group
                if p.exists()
            ]
            if not phrase_clip_paths:
                continue
            phrase_path = tmpdir / f"phrase_{phrase_idx:03d}.wav"
            if len(phrase_clip_paths) == 1:
                shutil.copy2(phrase_clip_paths[0], phrase_path)
            else:
                concatenate_clips(
                    phrase_clip_paths, phrase_path,
                    crossfade_ms=word_crossfade_ms,
                )
            phrase_paths.append(phrase_path)

        # === Phase C: Prosodic dynamics on phrase WAVs ===
        if prosodic_dynamics and phrase_paths:
            for phrase_path in phrase_paths:
                if not phrase_path.exists():
                    continue
                try:
                    dur = get_duration(phrase_path)
                    if dur > 0.3:
                        fade_start = dur * 0.7
                        softened = phrase_path.parent / f"dyn_{phrase_path.name}"
                        cmd = [
                            "ffmpeg", "-y", "-i", str(phrase_path),
                            "-af",
                            (
                                f"volume=enable='between(t,0,{dur*0.2:.4f})':"
                                f"volume=1.12dB,"
                                f"volume=enable='gte(t,{fade_start:.4f})':"
                                f"volume=-3dB"
                            ),
                            "-c:a", "pcm_s16le",
                            str(softened),
                        ]
                        result_proc = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=30
                        )
                        if result_proc.returncode == 0:
                            shutil.move(softened, phrase_path)
                except Exception:
                    pass

        # Group phrases into sentences, compute gap durations
        sentence_groups = _group_into_sentences(
            list(range(len(phrase_paths))), pps_min, pps_max, rng
        )

        # === Phase D: Build gaps with room tone + breaths ===
        gap_durations = []
        gap_types = []  # 'phrase' or 'sentence'
        ordered_phrase_paths = []
        for sent_idx, sent_phrase_indices in enumerate(sentence_groups):
            for i, phrase_idx in enumerate(sent_phrase_indices):
                if phrase_idx < len(phrase_paths):
                    ordered_phrase_paths.append(phrase_paths[phrase_idx])
                    is_last_in_sentence = (i == len(sent_phrase_indices) - 1)
                    is_last_sentence = (sent_idx == len(sentence_groups) - 1)
                    if not (is_last_in_sentence and is_last_sentence):
                        if is_last_in_sentence:
                            gap_durations.append(rng.uniform(sp_min, sp_max))
                            gap_types.append("sentence")
                        else:
                            gap_durations.append(rng.uniform(pp_min, pp_max))
                            gap_types.append("phrase")

        # Build gap clips (room tone or silence, optionally with breaths)
        all_breath_clips = [
            bp for bps in source_breaths.values() for bp in bps
        ]
        final_clips_with_gaps = []
        for i, phrase_path in enumerate(ordered_phrase_paths):
            final_clips_with_gaps.append(phrase_path)
            if i < len(gap_durations):
                gap_ms = gap_durations[i]
                gap_path = tmpdir / f"gap_{i:04d}.wav"

                try:
                    # Try room tone, fall back to silence
                    if source_room_tones:
                        rt_source = list(source_room_tones.values())[
                            i % len(source_room_tones)
                        ]
                        generate_silence(gap_path, gap_ms)
                        mixed_gap = tmpdir / f"gap_mixed_{i:04d}.wav"
                        mix_audio(gap_path, rt_source, mixed_gap,
                                  secondary_volume_db=0)
                        shutil.move(mixed_gap, gap_path)
                    else:
                        generate_silence(gap_path, gap_ms)
                except Exception:
                    # Last resort: plain silence
                    try:
                        generate_silence(gap_path, gap_ms)
                    except Exception:
                        continue

                # Optionally prepend a breath at phrase boundaries
                if (all_breath_clips
                        and i < len(gap_types)
                        and gap_types[i] == "phrase"
                        and rng.random() < breath_probability):
                    try:
                        breath_clip = rng.choice(all_breath_clips)
                        breath_gap = tmpdir / f"breath_gap_{i:04d}.wav"
                        concatenate_clips(
                            [breath_clip, gap_path], breath_gap,
                            crossfade_ms=10,
                        )
                        gap_path = breath_gap
                    except Exception:
                        pass

                final_clips_with_gaps.append(gap_path)

        # Final concatenation
        concatenated_path = output_dir / "concatenated.wav"
        if final_clips_with_gaps:
            concatenate_clips(
                final_clips_with_gaps,
                concatenated_path,
                crossfade_ms=0,
            )

        # === Phase E: Mix pink noise bed under entire output ===
        if noise_level_db != 0 and concatenated_path.exists():
            try:
                dur = get_duration(concatenated_path)
                noise = generate_pink_noise(dur, 16000, seed=seed)
                noise_path = tmpdir / "noise_bed.wav"
                write_wav(noise_path, noise, 16000)
                mixed_path = tmpdir / "concatenated_mixed.wav"
                mix_audio(
                    concatenated_path, noise_path, mixed_path,
                    secondary_volume_db=noise_level_db,
                )
                shutil.move(mixed_path, concatenated_path)
            except Exception:
                logger.debug("Noise bed mixing failed, skipping")

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

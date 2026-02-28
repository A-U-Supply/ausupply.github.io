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

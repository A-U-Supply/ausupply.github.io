"""Audio processing via ffmpeg/ffprobe."""

import json
import shutil
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
    output = _run_ffprobe(path, "-show_format", "-show_streams")
    data = json.loads(output)
    # Try format duration first, fall back to first audio stream
    dur = data.get("format", {}).get("duration")
    if dur is None:
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio" and "duration" in stream:
                dur = stream["duration"]
                break
    if dur is None:
        return 0.0
    return float(dur)


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
    cmd.extend(["-c:a", "pcm_s16le", str(output_path)])

    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path


def generate_silence(output_path: Path, duration_ms: float, sample_rate: int = 16000) -> Path:
    """Generate a silent WAV file."""
    duration_s = duration_ms / 1000.0
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", f"{duration_s:.4f}",
        "-c:a", "pcm_s16le",
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
    """Concatenate audio clips with optional gaps and crossfade."""
    import tempfile

    if not clip_paths:
        raise ValueError("No clips to concatenate")

    if len(clip_paths) == 1:
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
                    silence_path = tmpdir / f"silence_{i:04d}.wav"
                    generate_silence(silence_path, gap_ms)
                    concat_list.append(silence_path)

        if crossfade_ms > 0:
            _concatenate_with_crossfade(concat_list, output_path, crossfade_ms)
        else:
            _concatenate_simple(concat_list, output_path)

    return output_path


def _concatenate_simple(clip_paths: list[Path], output_path: Path) -> None:
    """Concatenate via ffmpeg concat filter (robust for WAV files)."""
    n = len(clip_paths)
    inputs = []
    for clip in clip_paths:
        inputs.extend(["-i", str(clip)])

    # Use the concat filter instead of concat demuxer for WAV compatibility
    filter_str = "".join(f"[{i}:a]" for i in range(n))
    filter_str += f"concat=n={n}:v=0:a=1[out]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120).check_returncode()


def _concatenate_with_crossfade(
    clip_paths: list[Path], output_path: Path, crossfade_ms: float
) -> None:
    """Concatenate with acrossfade filters between clips."""
    n = len(clip_paths)

    if n <= 1:
        shutil.copy2(clip_paths[0], output_path)
        return

    # Get durations, drop clips with no measurable audio
    durations = []
    valid_paths = []
    for p in clip_paths:
        dur = get_duration(p)
        if dur > 0.001:
            durations.append(dur)
            valid_paths.append(p)
    clip_paths = valid_paths
    n = len(clip_paths)

    if n == 0:
        raise ValueError("No clips with non-zero duration to concatenate")
    if n == 1:
        shutil.copy2(clip_paths[0], output_path)
        return

    # acrossfade needs each clip > crossfade duration, and the chained
    # intermediate results can still produce zero frames for short clips.
    # Require each clip to be at least 3x the crossfade to be safe.
    min_dur = min(durations)
    safe_crossfade_ms = min(crossfade_ms, min_dur * 1000 / 3.0)
    if safe_crossfade_ms < 1:
        _concatenate_simple(clip_paths, output_path)
        return
    crossfade_s = safe_crossfade_ms / 1000.0

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
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    result.check_returncode()

    # ffmpeg can exit 0 but produce empty output when acrossfade filter
    # drops all frames (short clips in a chain). Fall back to simple concat.
    if output_path.stat().st_size <= 78:
        _concatenate_simple(clip_paths, output_path)


def pitch_shift_clip(input_path: Path, output_path: Path, semitones: float) -> Path:
    """Pitch-shift a WAV clip by the given number of semitones.

    Uses ffmpeg asetrate + aresample to change pitch without changing duration.
    If semitones is ~0, just copies the file.
    """
    if abs(semitones) < 0.01:
        shutil.copy2(input_path, output_path)
        return output_path

    # Get original sample rate via ffprobe
    output = _run_ffprobe(input_path, "-show_streams")
    data = json.loads(output)
    original_sr = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            original_sr = int(stream["sample_rate"])
            break
    if original_sr is None:
        raise ValueError(f"No audio stream found in {input_path}")

    # Compute new rate: original_sr * 2^(semitones/12)
    new_rate = original_sr * (2 ** (semitones / 12))

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"asetrate={new_rate:.2f},aresample={original_sr}",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path


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


def adjust_volume(input_path: Path, output_path: Path, db: float) -> Path:
    """Adjust volume by dB amount using ffmpeg volume filter."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"volume={db:.2f}dB",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path


def mix_audio(
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    secondary_volume_db: float = -40,
) -> Path:
    """Mix secondary audio under primary at the given volume level.

    Output duration matches the primary. Secondary is looped if shorter.
    """
    primary_dur = get_duration(primary_path)

    # Input 0: primary (as-is)
    # Input 1: secondary, volume-adjusted, looped via stream_loop
    cmd = [
        "ffmpeg", "-y",
        "-i", str(primary_path),
        "-stream_loop", "-1", "-i", str(secondary_path),
        "-filter_complex",
        f"[1:a]volume={secondary_volume_db:.2f}dB[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[out]",
        "-map", "[out]",
        "-t", f"{primary_dur:.4f}",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120).check_returncode()
    return output_path

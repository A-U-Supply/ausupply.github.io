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

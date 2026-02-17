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
    """Synthesize all 4 MIDI tracks into a single WAV."""
    synthesize = _import_synthesizer()
    return synthesize(midi_dir, output_path)


def build_mix_command(
    vocal_path: Path,
    midi_wav_path: Path,
    output_path: Path,
    vocal_db: float = 0,
    midi_db: float = -12,
) -> list[str]:
    """Build ffmpeg command to mix vocal over MIDI backing.

    Uses volume filters in dB for predictable levels. Default puts MIDI
    12 dB below the vocals so the singing is clearly audible.
    """
    return [
        "ffmpeg", "-y",
        "-i", str(vocal_path),
        "-i", str(midi_wav_path),
        "-filter_complex",
        f"[0]aresample=16000,volume={vocal_db}dB[v];"
        f"[1]aresample=16000,volume={midi_db}dB[m];"
        f"[v][m]amix=inputs=2:duration=longest:normalize=0[out]",
        "-map", "[out]",
        "-ar", "16000",
        str(output_path),
    ]


def mix_tracks(
    vocal_path: Path,
    midi_dir: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Produce the two output files: a cappella and full mix."""
    output_dir.mkdir(parents=True, exist_ok=True)
    acappella_path = output_dir / "acappella.wav"
    full_mix_path = output_dir / "full_mix.wav"

    # Copy a cappella
    subprocess.run(["cp", str(vocal_path), str(acappella_path)], capture_output=True)

    # Synthesize MIDI backing
    midi_wav = output_dir / "midi_backing.wav"
    try:
        success = synthesize_midi_backing(midi_dir, midi_wav)
    except Exception as e:
        logger.warning(f"MIDI synthesis failed: {e}")
        success = False

    if success and midi_wav.exists():
        cmd = build_mix_command(acappella_path, midi_wav, full_mix_path)
        subprocess.run(cmd, capture_output=True)
    else:
        logger.warning("MIDI synthesis failed, using a cappella as full mix")
        subprocess.run(["cp", str(acappella_path), str(full_mix_path)], capture_output=True)

    return full_mix_path, acappella_path

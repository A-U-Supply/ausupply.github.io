"""Python wrapper for Magenta.js MIDI extension."""
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

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
    """Extend MIDI tracks using Magenta.js."""
    if scale_intervals is None:
        scale_intervals = [0, 2, 4, 5, 7, 9, 11]
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
        logger.warning("Falling back to simple loop")
        return _fallback_loop(
            melody_path, drums_path, bass_path, chords_path, output_dir
        )

    # Magenta prints initialization logs to stdout before the JSON summary.
    # Extract the last line that looks like JSON.
    json_lines = [
        line for line in result.stdout.strip().split("\n")
        if line.strip().startswith("{")
    ]
    if json_lines:
        try:
            summary = json.loads(json_lines[-1])
            logger.info(f"Extended: {summary}")
            return summary
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse Magenta output: {result.stdout}")
    return {}


def _fallback_loop(melody_path, drums_path, bass_path, chords_path, output_dir):
    """Copy originals as fallback."""
    import shutil
    for src, name in [
        (melody_path, "melody.mid"),
        (drums_path, "drums.mid"),
        (bass_path, "bass.mid"),
        (chords_path, "chords.mid"),
    ]:
        shutil.copy2(src, output_dir / name)
    return {"fallback": True}

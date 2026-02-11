"""Synthesize MIDI files to a mixed audio preview using sine waves."""
import logging
from pathlib import Path

import numpy as np
import pretty_midi
from scipy.io import wavfile

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050
MAX_DURATION = 30  # seconds


def _synthesize_drums(midi_obj, fs):
    """Synthesize drum track using noise bursts (kick/snare/hihat)."""
    duration = midi_obj.get_end_time() + 1.0
    audio = np.zeros(int(duration * fs))

    for inst in midi_obj.instruments:
        if not inst.is_drum:
            continue
        for note in inst.notes:
            start = int(note.start * fs)
            vel = note.velocity / 127.0

            if note.pitch in (35, 36):  # kick
                length = int(0.08 * fs)
                t = np.linspace(0, 0.08, length)
                burst = np.sin(2 * np.pi * 80 * t * np.exp(-t * 30)) * np.exp(-t * 25)
            elif note.pitch in (38, 40):  # snare
                length = int(0.1 * fs)
                t = np.linspace(0, 0.1, length)
                burst = (np.random.randn(length) * 0.7 + np.sin(2 * np.pi * 180 * t) * 0.3) * np.exp(-t * 20)
            elif note.pitch in (42, 44, 46):  # hihat
                length = int(0.05 * fs)
                t = np.linspace(0, 0.05, length)
                burst = np.random.randn(length) * np.exp(-t * 60) * 0.5
            else:  # other percussion
                length = int(0.06 * fs)
                t = np.linspace(0, 0.06, length)
                burst = np.random.randn(length) * np.exp(-t * 40) * 0.4

            end = min(start + length, len(audio))
            audio[start:end] += burst[:end - start] * vel

    return audio


def synthesize_preview(midi_dir: Path, output_path: Path) -> bool:
    """Load 4 MIDI tracks, synthesize, mix, and write a WAV preview."""
    track_names = ["melody", "chords", "bass", "drums"]
    tracks = []

    for name in track_names:
        midi_file = midi_dir / f"{name}.mid"
        if not midi_file.exists():
            logger.warning(f"Missing {midi_file}, skipping")
            continue

        mid = pretty_midi.PrettyMIDI(str(midi_file))

        if name == "drums":
            audio = _synthesize_drums(mid, SAMPLE_RATE)
        else:
            audio = mid.synthesize(fs=SAMPLE_RATE)
            audio = np.nan_to_num(audio, nan=0.0)

        tracks.append(audio)
        logger.info(f"Synthesized {name}: {len(audio) / SAMPLE_RATE:.1f}s")

    if not tracks:
        logger.error("No tracks to mix")
        return False

    # Pad to same length, mix, and trim
    max_len = max(len(t) for t in tracks)
    max_samples = int(MAX_DURATION * SAMPLE_RATE)
    mix_len = min(max_len, max_samples)

    mixed = np.zeros(mix_len)
    for t in tracks:
        end = min(len(t), mix_len)
        mixed[:end] += t[:end]

    # Normalize
    peak = np.abs(mixed).max()
    if peak > 0:
        mixed = mixed / peak * 0.9

    wavfile.write(str(output_path), SAMPLE_RATE, (mixed * 32767).astype(np.int16))
    logger.info(f"Preview written: {output_path} ({mix_len / SAMPLE_RATE:.1f}s)")
    return True

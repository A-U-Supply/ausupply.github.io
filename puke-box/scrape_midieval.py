"""Scrape #midieval Slack channel and archive MIDI bot output."""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PUKE_BOX_DIR = Path(__file__).parent
MANIFEST_PATH = PUKE_BOX_DIR / "manifest.json"


def parse_midi_message(text: str) -> dict | None:
    """Parse a Daily MIDI message into structured metadata. Returns None if not a match."""
    header = re.search(
        r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)', text
    )
    if not header:
        return None

    scale, root, tempo = header.group(1), header.group(2), int(header.group(3))

    desc_match = re.search(r'_(.+?)_', text)
    description = desc_match.group(1) if desc_match else ""

    chords_match = re.search(r':musical_score: Chords\s*—\s*(.+)', text)
    chords = chords_match.group(1).split() if chords_match else []

    melody_match = re.search(r'Melody.*?MIDI\s+(\d+)', text)
    melody_instrument = int(melody_match.group(1)) if melody_match else 0

    temp_match = re.search(r'temperature\s+([\d.]+)', text)
    temperature = float(temp_match.group(1)) if temp_match else 1.0

    chord_instrument = 0

    return {
        "scale": scale,
        "root": root,
        "tempo": tempo,
        "description": description,
        "chords": chords,
        "melody_instrument": melody_instrument,
        "chord_instrument": chord_instrument,
        "temperature": temperature,
    }

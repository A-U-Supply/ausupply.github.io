"""Parse MIDI files into structured note sequences."""
from dataclasses import dataclass
from pathlib import Path

import pretty_midi


@dataclass
class Note:
    """A single MIDI note."""
    pitch: int
    start: float
    end: float
    velocity: int

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class MidiTrack:
    """Parsed MIDI track."""
    notes: list[Note]
    tempo: float
    program: int
    is_drum: bool
    total_duration: float


def parse_midi(path: Path) -> MidiTrack:
    """Parse a MIDI file into a MidiTrack."""
    mid = pretty_midi.PrettyMIDI(str(path))

    try:
        tempo = mid.estimate_tempo()
    except ValueError:
        # estimate_tempo fails with fewer than two notes; fall back to
        # the tempo embedded in the MIDI file's tempo-change map.
        tempo_changes = mid.get_tempo_changes()
        tempo = tempo_changes[1][0] if len(tempo_changes[1]) > 0 else 120.0
    notes = []
    program = 0
    is_drum = False

    if mid.instruments:
        # Merge all non-drum instruments (Magenta may split seed + continuation
        # across tracks if program numbers differ)
        for inst in mid.instruments:
            if inst.is_drum:
                continue
            if not is_drum and not notes:
                program = inst.program
                is_drum = inst.is_drum
            for n in inst.notes:
                notes.append(Note(
                    pitch=n.pitch,
                    start=round(n.start, 4),
                    end=round(n.end, 4),
                    velocity=n.velocity,
                ))
        notes.sort(key=lambda n: n.start)

    total_duration = mid.get_end_time()
    return MidiTrack(
        notes=notes,
        tempo=round(tempo),
        program=program,
        is_drum=is_drum,
        total_duration=total_duration,
    )

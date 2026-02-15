"""Core data types for glottisdale."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Phoneme:
    """A single phoneme with timing."""
    label: str       # ARPABET e.g. "AH0", or IPA if BFA
    start: float     # seconds
    end: float       # seconds


@dataclass
class Syllable:
    """A group of phonemes forming one syllable."""
    phonemes: list[Phoneme]
    start: float        # first phoneme start (seconds)
    end: float          # last phoneme end (seconds)
    word: str           # parent word
    word_index: int     # position in transcript


@dataclass
class Clip:
    """An audio clip containing one or more syllables."""
    syllables: list[Syllable]
    start: float        # with padding applied (seconds)
    end: float          # with padding applied (seconds)
    source: str         # input filename
    output_path: Path = field(default_factory=lambda: Path())


@dataclass
class Result:
    """Output of the glottisdale pipeline."""
    clips: list[Clip]
    concatenated: Path
    transcript: str
    manifest: dict

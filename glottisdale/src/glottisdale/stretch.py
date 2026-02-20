"""Stretch selection logic for time-stretch features."""

import random
from dataclasses import dataclass
from pathlib import Path

from glottisdale.types import Clip


@dataclass
class StretchConfig:
    """Configuration for which syllables/words get stretched."""
    random_stretch: float | None = None       # probability 0-1
    alternating_stretch: int | None = None    # every Nth syllable
    boundary_stretch: int | None = None       # first/last N in each word
    word_stretch: float | None = None         # probability 0-1 for whole words
    stretch_factor: tuple[float, float] = (2.0, 2.0)  # (min, max) range


def parse_stretch_factor(s: str) -> tuple[float, float]:
    """Parse stretch factor string: '2.0' or '1.5-3.0' into (min, max)."""
    if "-" in s:
        # Check if it's a negative number vs a range
        parts = s.split("-")
        # Filter out empty strings from leading minus
        parts = [p for p in parts if p]
        if len(parts) == 2 and not s.startswith("-"):
            return float(parts[0]), float(parts[1])
    return float(s), float(s)


def resolve_stretch_factor(
    factor_range: tuple[float, float], rng: random.Random
) -> float:
    """Pick a stretch factor from the range. Fixed if min==max."""
    if factor_range[0] == factor_range[1]:
        return factor_range[0]
    return rng.uniform(factor_range[0], factor_range[1])


def should_stretch_syllable(
    syllable_index: int,
    word_syllable_index: int,
    word_syllable_count: int,
    rng: random.Random,
    config: StretchConfig,
) -> bool:
    """Determine if a syllable should be stretched based on active modes.

    Returns True if ANY active mode selects this syllable.
    """
    if config.random_stretch is not None:
        if rng.random() < config.random_stretch:
            return True

    if config.alternating_stretch is not None:
        if syllable_index % config.alternating_stretch == 0:
            return True

    if config.boundary_stretch is not None:
        n = config.boundary_stretch
        if (word_syllable_index < n
                or word_syllable_index >= word_syllable_count - n):
            return True

    return False


def parse_count_range(s: str) -> tuple[int, int]:
    """Parse count string: '2' or '1-3' into (min, max)."""
    if "-" in s:
        parts = s.split("-", 1)
        return int(parts[0]), int(parts[1])
    val = int(s)
    return val, val


def apply_stutter(
    syllable_paths: list[Path],
    probability: float,
    count_range: tuple[int, int],
    rng: random.Random,
) -> list[Path]:
    """Duplicate syllable clips in-place for stuttering effect.

    Returns new list with stuttered syllables repeated.
    """
    result = []
    for path in syllable_paths:
        result.append(path)
        if rng.random() < probability:
            n = rng.randint(count_range[0], count_range[1])
            result.extend([path] * n)
    return result


def apply_word_repeat(
    words: list[Clip],
    probability: float,
    count_range: tuple[int, int],
    style: str,
    rng: random.Random,
) -> list[Clip]:
    """Duplicate words in the word list for repetition effect.

    style='exact': duplicate the same Clip (same WAV file).
    style='resample': not implemented here — caller handles re-assembly.
    Returns new list with repeated words inserted after originals.
    """
    result = []
    for word in words:
        result.append(word)
        if rng.random() < probability:
            n = rng.randint(count_range[0], count_range[1])
            if style == "exact":
                result.extend([word] * n)
            # 'resample' handled by caller in pipeline
    return result

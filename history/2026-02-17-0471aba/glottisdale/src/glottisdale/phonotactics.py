"""Phonotactic scoring for natural-sounding syllable ordering."""

import random

from glottisdale.types import Syllable

# Sonority scale for ARPABET phonemes (higher = more sonorous)
_SONORITY = {}

# 1: Stops
for p in ("P", "B", "T", "D", "K", "G"):
    _SONORITY[p] = 1

# 2: Affricates
for p in ("CH", "JH"):
    _SONORITY[p] = 2

# 3: Fricatives
for p in ("F", "V", "TH", "DH", "S", "Z", "SH", "ZH", "HH"):
    _SONORITY[p] = 3

# 4: Nasals
for p in ("M", "N", "NG"):
    _SONORITY[p] = 4

# 5: Liquids
for p in ("L", "R"):
    _SONORITY[p] = 5

# 6: Glides
for p in ("W", "Y"):
    _SONORITY[p] = 6

# Illegal English onsets (these sounds cannot start a word/syllable)
_ILLEGAL_ONSETS = {"NG", "ZH"}


def sonority(label: str) -> int:
    """Return sonority value for an ARPABET phoneme label.

    Strips stress digits (e.g. 'AH0' -> vowel). Returns 0 for unknown.
    """
    # Strip trailing stress digits for vowel lookup
    base = label.rstrip("012")
    if base in _SONORITY:
        return _SONORITY[base]
    # Check if it's a vowel (anything with a stress digit, or known vowel base)
    if label != base or base in (
        "AA", "AE", "AH", "AO", "AW", "AY",
        "EH", "ER", "EY", "IH", "IY",
        "OW", "OY", "UH", "UW",
    ):
        return 7
    return 0


def score_junction(syl_a: Syllable, syl_b: Syllable) -> int:
    """Score the phonotactic quality of the junction between two syllables.

    Higher scores = more natural-sounding transitions.
    """
    if not syl_a.phonemes or not syl_b.phonemes:
        return 0

    last_phone = syl_a.phonemes[-1].label
    first_phone = syl_b.phonemes[0].label

    score = 0

    # Illegal onset penalty
    base_first = first_phone.rstrip("012")
    if base_first in _ILLEGAL_ONSETS:
        score -= 2

    # Hiatus penalty (vowel-vowel boundary)
    if sonority(last_phone) == 7 and sonority(first_phone) == 7:
        score -= 1

    # Sonority contour: coda should fall, onset should rise toward nucleus
    # A good junction has falling sonority at end of syl_a, low at boundary,
    # rising into syl_b. Simplified: lower sonority at boundary = better.
    boundary_sonority = sonority(last_phone) + sonority(first_phone)
    if boundary_sonority <= 8:  # Both consonantal
        score += 1
    elif boundary_sonority >= 12:  # Both very sonorous
        score -= 1

    return score


def order_syllables(
    syllables: list[Syllable],
    seed: int | None = None,
    attempts: int = 5,
) -> list[Syllable]:
    """Reorder syllables to maximize phonotactic junction quality.

    Tries `attempts` random permutations and returns the best-scoring one.
    """
    if len(syllables) <= 1:
        return list(syllables)

    rng = random.Random(seed)

    def total_score(ordering: list[Syllable]) -> int:
        return sum(
            score_junction(ordering[i], ordering[i + 1])
            for i in range(len(ordering) - 1)
        )

    best = list(syllables)
    best_score = total_score(best)

    for _ in range(attempts):
        candidate = list(syllables)
        rng.shuffle(candidate)
        s = total_score(candidate)
        if s > best_score:
            best = candidate
            best_score = s

    return best

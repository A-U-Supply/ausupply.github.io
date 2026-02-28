"""Syllabification: words with timestamps → syllable boundaries."""

from pathlib import Path
from g2p_en import G2p
from glottisdale.types import Phoneme, Syllable

# Import vendored ARPABET syllabifier
from glottisdale.syllabify_arpabet import syllabify as _arpabet_syllabify

_g2p = None


def _get_g2p() -> G2p:
    """Lazy-init g2p_en (downloads model on first use)."""
    global _g2p
    if _g2p is None:
        _g2p = G2p()
    return _g2p


def syllabify_word(
    phonemes: list[str],
    word_start: float,
    word_end: float,
    word: str,
    word_index: int,
) -> list[Syllable]:
    """Split a word's phonemes into syllables with estimated timestamps.

    Timestamps are distributed proportionally across syllables based on
    phoneme count per syllable.
    """
    if not phonemes:
        return []

    try:
        syl_tuples = _arpabet_syllabify(phonemes)
    except (ValueError, KeyError):
        # Fallback: treat entire word as one syllable
        syl_tuples = [([], phonemes, [])]

    if not syl_tuples:
        syl_tuples = [([], phonemes, [])]

    # Count phonemes per syllable for proportional timing
    syl_phoneme_lists = [onset + nucleus + coda for onset, nucleus, coda in syl_tuples]
    total_phonemes = sum(len(s) for s in syl_phoneme_lists)
    if total_phonemes == 0:
        total_phonemes = 1

    word_duration = word_end - word_start
    syllables = []
    current_time = word_start

    for syl_phones in syl_phoneme_lists:
        proportion = len(syl_phones) / total_phonemes
        syl_duration = word_duration * proportion
        syl_end = current_time + syl_duration

        # Create Phoneme objects with evenly distributed times within syllable
        phoneme_objects = []
        if syl_phones:
            ph_dur = syl_duration / len(syl_phones)
            ph_time = current_time
            for label in syl_phones:
                phoneme_objects.append(Phoneme(
                    label=label,
                    start=round(ph_time, 4),
                    end=round(ph_time + ph_dur, 4),
                ))
                ph_time += ph_dur

        syllables.append(Syllable(
            phonemes=phoneme_objects,
            start=round(current_time, 4),
            end=round(syl_end, 4),
            word=word,
            word_index=word_index,
        ))
        current_time = syl_end

    return syllables


def syllabify_words(
    words: list[dict],
) -> list[Syllable]:
    """Convert word-level timestamps to syllable-level timestamps.

    Args:
        words: List of dicts with 'word', 'start', 'end' keys
               (as returned by Whisper with word_timestamps=True).

    Returns:
        Flat list of Syllable objects across all words.
    """
    g2p = _get_g2p()
    all_syllables = []

    for i, w in enumerate(words):
        text = w["word"].strip()
        if not text:
            continue

        # g2p_en returns list of phonemes + spaces between words
        raw_phonemes = g2p(text)
        phonemes = [p for p in raw_phonemes if p.strip() and p != " "]

        if not phonemes:
            continue

        syls = syllabify_word(
            phonemes=phonemes,
            word_start=w["start"],
            word_end=w["end"],
            word=text,
            word_index=i,
        )
        all_syllables.extend(syls)

    return all_syllables

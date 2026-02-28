"""Tests for syllabification wrapper."""

from glottisdale.types import Phoneme, Syllable
from glottisdale.syllabify import syllabify_word, syllabify_words


def test_syllabify_word_single_syllable():
    """'cat' = K AE1 T → 1 syllable."""
    phonemes = ["K", "AE1", "T"]
    word_start = 0.0
    word_end = 0.3
    syllables = syllabify_word(phonemes, word_start, word_end, "cat", word_index=0)
    assert len(syllables) == 1
    assert syllables[0].word == "cat"
    assert syllables[0].start == 0.0
    assert syllables[0].end == 0.3
    assert len(syllables[0].phonemes) == 3


def test_syllabify_word_two_syllables():
    """'camel' = K AE1 M AH0 L → 2 syllables."""
    phonemes = ["K", "AE1", "M", "AH0", "L"]
    syllables = syllabify_word(phonemes, 0.0, 0.5, "camel", word_index=1)
    assert len(syllables) == 2
    # First syllable gets proportional time: 2 phonemes / 5 total * 0.5s = 0.2s
    # Second syllable: 3 phonemes / 5 total * 0.5s = 0.3s
    assert syllables[0].start == 0.0
    assert abs(syllables[0].end - 0.2) < 0.001
    assert abs(syllables[1].start - 0.2) < 0.001
    assert syllables[1].end == 0.5


def test_syllabify_word_three_syllables():
    """'banana' = B AH0 N AE1 N AH0 → 3 syllables."""
    phonemes = ["B", "AH0", "N", "AE1", "N", "AH0"]
    syllables = syllabify_word(phonemes, 0.0, 0.6, "banana", word_index=0)
    assert len(syllables) == 3


def test_syllabify_words():
    """Process multiple words into a flat syllable list."""
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
    ]
    syllables = syllabify_words(words)
    # "hello" = HH AH0 L OW1 → 2 syllables
    # "world" = W ER1 L D → 1 syllable
    assert len(syllables) == 3
    assert syllables[0].word == "hello"
    assert syllables[0].word_index == 0
    assert syllables[2].word == "world"
    assert syllables[2].word_index == 1


def test_syllabify_word_unknown_word():
    """Unknown word (not in g2p) should still produce at least 1 syllable."""
    syllables = syllabify_word(
        ["AH0"], 0.0, 0.1, "xyzzy", word_index=0
    )
    assert len(syllables) >= 1

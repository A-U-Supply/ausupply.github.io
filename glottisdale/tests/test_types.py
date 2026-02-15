"""Tests for core data types."""

from pathlib import Path
from glottisdale.types import Phoneme, Syllable, Clip, Result


def test_phoneme_creation():
    p = Phoneme(label="AH0", start=0.1, end=0.2)
    assert p.label == "AH0"
    assert p.start == 0.1
    assert p.end == 0.2


def test_syllable_creation():
    p1 = Phoneme("HH", 0.1, 0.15)
    p2 = Phoneme("AH0", 0.15, 0.25)
    syl = Syllable(phonemes=[p1, p2], start=0.1, end=0.25, word="hello", word_index=0)
    assert len(syl.phonemes) == 2
    assert syl.word == "hello"


def test_clip_creation():
    p = Phoneme("AH0", 0.1, 0.2)
    syl = Syllable([p], 0.1, 0.2, "a", 0)
    clip = Clip(syllables=[syl], start=0.075, end=0.225, source="test.wav")
    assert clip.source == "test.wav"
    assert clip.start == 0.075


def test_result_creation():
    result = Result(clips=[], concatenated=Path("out.ogg"), transcript="hello", manifest={})
    assert result.transcript == "hello"
    assert result.concatenated == Path("out.ogg")

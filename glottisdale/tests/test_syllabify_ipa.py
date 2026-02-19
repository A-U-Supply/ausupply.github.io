"""Tests for IPA sonority-based syllabifier."""

import pytest

from glottisdale.types import Phoneme, Syllable
from glottisdale.syllabify_ipa import (
    pg16_sonority,
    syllabify_ipa,
    _is_vowel,
    _valid_onset,
)


def _ph(label: str, start: float, end: float) -> Phoneme:
    """Helper to create a Phoneme."""
    return Phoneme(label=label, start=start, end=end)


class TestPg16Sonority:
    def test_stops_lowest(self):
        assert pg16_sonority("voiced_stops") == 0

    def test_affricates(self):
        assert pg16_sonority("affricates") == 1

    def test_fricatives(self):
        assert pg16_sonority("voiceless_fricatives") == 2
        assert pg16_sonority("voiced_fricatives") == 2

    def test_nasals(self):
        assert pg16_sonority("nasals") == 3

    def test_laterals_and_rhotics(self):
        assert pg16_sonority("laterals") == 4
        assert pg16_sonority("rhotics") == 4

    def test_glides_and_approximants(self):
        assert pg16_sonority("glides") == 5
        assert pg16_sonority("approximants") == 5

    def test_vowels_highest(self):
        assert pg16_sonority("central_vowels") == 6
        assert pg16_sonority("front_vowels") == 6
        assert pg16_sonority("back_vowels") == 6
        assert pg16_sonority("diphthongs") == 6
        assert pg16_sonority("vowels") == 6

    def test_silence(self):
        assert pg16_sonority("silence") == -1

    def test_unknown_defaults_to_1(self):
        assert pg16_sonority("unknown_group") == 1

    def test_sonority_ordering(self):
        """Verify stops < fricatives < nasals < liquids < glides < vowels."""
        assert pg16_sonority("voiced_stops") < pg16_sonority("voiceless_fricatives")
        assert pg16_sonority("voiceless_fricatives") < pg16_sonority("nasals")
        assert pg16_sonority("nasals") < pg16_sonority("laterals")
        assert pg16_sonority("laterals") < pg16_sonority("glides")
        assert pg16_sonority("glides") < pg16_sonority("vowels")


class TestIsVowel:
    def test_vowel_groups(self):
        assert _is_vowel("central_vowels")
        assert _is_vowel("front_vowels")
        assert _is_vowel("back_vowels")
        assert _is_vowel("diphthongs")
        assert _is_vowel("vowels")

    def test_non_vowel_groups(self):
        assert not _is_vowel("voiced_stops")
        assert not _is_vowel("nasals")
        assert not _is_vowel("laterals")
        assert not _is_vowel("silence")


class TestValidOnset:
    def test_empty_valid(self):
        assert _valid_onset([])

    def test_single_consonant_valid(self):
        assert _valid_onset(["voiced_stops"])

    def test_rising_sonority_valid(self):
        # stop + liquid = valid (e.g., "pl", "br")
        assert _valid_onset(["voiced_stops", "laterals"])

    def test_falling_sonority_invalid(self):
        # liquid + stop = invalid onset
        assert not _valid_onset(["laterals", "voiced_stops"])

    def test_equal_sonority_valid(self):
        # same level = valid
        assert _valid_onset(["laterals", "rhotics"])


class TestSyllabifyIpa:
    def test_single_syllable_cvc(self):
        """'cat' = k æ t → 1 syllable."""
        phonemes = [
            _ph("k", 0.0, 0.1),
            _ph("æ", 0.1, 0.25),
            _ph("t", 0.25, 0.35),
        ]
        groups = ["voiced_stops", "front_vowels", "voiced_stops"]
        syls = syllabify_ipa(phonemes, groups, "cat", 0)
        assert len(syls) == 1
        assert syls[0].start == 0.0
        assert syls[0].end == 0.35
        assert len(syls[0].phonemes) == 3

    def test_two_syllable_word(self):
        """'butter' = b ʌ t ə ɹ → 2 syllables (bʌt.əɹ)."""
        phonemes = [
            _ph("b", 0.0, 0.05),
            _ph("ʌ", 0.05, 0.15),
            _ph("t", 0.15, 0.22),
            _ph("ə", 0.22, 0.30),
            _ph("ɹ", 0.30, 0.38),
        ]
        groups = [
            "voiced_stops", "central_vowels", "voiced_stops",
            "central_vowels", "rhotics",
        ]
        syls = syllabify_ipa(phonemes, groups, "butter", 0)
        assert len(syls) == 2
        # First syllable should start at 0.0
        assert syls[0].start == 0.0
        # Second syllable should end at 0.38
        assert syls[1].end == 0.38

    def test_three_syllable_word(self):
        """'beautiful' = b j uː t ɪ f ə l → 3 syllables."""
        phonemes = [
            _ph("b", 0.0, 0.04),
            _ph("j", 0.04, 0.08),
            _ph("uː", 0.08, 0.18),
            _ph("t", 0.18, 0.24),
            _ph("ɪ", 0.24, 0.32),
            _ph("f", 0.32, 0.38),
            _ph("ə", 0.38, 0.44),
            _ph("l", 0.44, 0.50),
        ]
        groups = [
            "voiced_stops", "glides", "back_vowels",
            "voiced_stops", "front_vowels",
            "voiceless_fricatives", "central_vowels", "laterals",
        ]
        syls = syllabify_ipa(phonemes, groups, "beautiful", 0)
        assert len(syls) == 3

    def test_single_vowel_word(self):
        """'a' = ə → 1 syllable."""
        phonemes = [_ph("ə", 0.0, 0.1)]
        groups = ["central_vowels"]
        syls = syllabify_ipa(phonemes, groups, "a", 0)
        assert len(syls) == 1
        assert syls[0].phonemes == phonemes

    def test_consonant_only_word(self):
        """All consonants → 1 syllable (fallback)."""
        phonemes = [
            _ph("s", 0.0, 0.1),
            _ph("t", 0.1, 0.2),
        ]
        groups = ["voiceless_fricatives", "voiced_stops"]
        syls = syllabify_ipa(phonemes, groups, "st", 0)
        assert len(syls) == 1
        assert len(syls[0].phonemes) == 2

    def test_consonant_cluster_onset(self):
        """'string' = s t ɹ ɪ ŋ → 1 syllable (str- onset)."""
        phonemes = [
            _ph("s", 0.0, 0.05),
            _ph("t", 0.05, 0.10),
            _ph("ɹ", 0.10, 0.15),
            _ph("ɪ", 0.15, 0.25),
            _ph("ŋ", 0.25, 0.33),
        ]
        groups = [
            "voiceless_fricatives", "voiced_stops", "rhotics",
            "front_vowels", "nasals",
        ]
        syls = syllabify_ipa(phonemes, groups, "string", 0)
        assert len(syls) == 1

    def test_silence_phonemes_filtered(self):
        """Silence phonemes should be excluded."""
        phonemes = [
            _ph("", 0.0, 0.05),
            _ph("k", 0.05, 0.1),
            _ph("æ", 0.1, 0.2),
            _ph("t", 0.2, 0.3),
            _ph("", 0.3, 0.35),
        ]
        groups = ["silence", "voiced_stops", "front_vowels", "voiced_stops", "silence"]
        syls = syllabify_ipa(phonemes, groups, "cat", 0)
        assert len(syls) == 1
        # Should only have 3 non-silence phonemes
        assert len(syls[0].phonemes) == 3

    def test_real_timestamps_preserved(self):
        """BFA timestamps should pass through unchanged (not proportional)."""
        phonemes = [
            _ph("h", 0.033, 0.067),
            _ph("ɛ", 0.067, 0.150),
            _ph("l", 0.150, 0.200),
            _ph("oʊ", 0.200, 0.350),
        ]
        groups = ["voiceless_fricatives", "front_vowels", "laterals", "diphthongs"]
        syls = syllabify_ipa(phonemes, groups, "hello", 0)
        assert len(syls) == 2
        # First syllable: h + ɛ (+ possibly l as coda)
        # Second syllable: oʊ (+ possibly l as onset)
        # Timestamps should be exactly as given, not recalculated
        assert syls[0].start == 0.033
        assert syls[-1].end == 0.350

    def test_empty_phonemes(self):
        syls = syllabify_ipa([], [], "empty", 0)
        assert syls == []

    def test_mismatched_lengths_raises(self):
        phonemes = [_ph("k", 0.0, 0.1)]
        groups = ["voiced_stops", "extra"]
        with pytest.raises(ValueError, match="must have same length"):
            syllabify_ipa(phonemes, groups, "bad", 0)

    def test_word_metadata(self):
        """Syllables carry correct word and word_index."""
        phonemes = [
            _ph("b", 0.0, 0.05),
            _ph("ʌ", 0.05, 0.15),
            _ph("t", 0.15, 0.22),
            _ph("ə", 0.22, 0.30),
            _ph("ɹ", 0.30, 0.38),
        ]
        groups = [
            "voiced_stops", "central_vowels", "voiced_stops",
            "central_vowels", "rhotics",
        ]
        syls = syllabify_ipa(phonemes, groups, "butter", 5)
        for syl in syls:
            assert syl.word == "butter"
            assert syl.word_index == 5

    def test_all_silence_returns_empty(self):
        """All-silence input should return empty list."""
        phonemes = [_ph("", 0.0, 0.1), _ph("", 0.1, 0.2)]
        groups = ["silence", "silence"]
        syls = syllabify_ipa(phonemes, groups, "silence", 0)
        assert syls == []

    def test_diphthong_as_nucleus(self):
        """Diphthongs should be treated as vowel nuclei."""
        phonemes = [
            _ph("b", 0.0, 0.05),
            _ph("aɪ", 0.05, 0.20),
            _ph("t", 0.20, 0.28),
        ]
        groups = ["voiced_stops", "diphthongs", "voiced_stops"]
        syls = syllabify_ipa(phonemes, groups, "bite", 0)
        assert len(syls) == 1
        assert len(syls[0].phonemes) == 3

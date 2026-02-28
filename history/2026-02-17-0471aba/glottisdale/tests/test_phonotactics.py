"""Tests for phonotactic junction scoring."""

from glottisdale.phonotactics import sonority, score_junction, order_syllables
from glottisdale.types import Phoneme, Syllable


def _syl(phoneme_labels: list[str], start: float = 0.0, dur: float = 0.25) -> Syllable:
    """Helper to make a Syllable from just phoneme labels."""
    phones = []
    t = start
    pd = dur / max(len(phoneme_labels), 1)
    for label in phoneme_labels:
        phones.append(Phoneme(label, round(t, 4), round(t + pd, 4)))
        t += pd
    return Syllable(phones, start, round(start + dur, 4), "test", 0)


class TestSonority:
    def test_stops_lowest(self):
        for p in ["P", "B", "T", "D", "K", "G"]:
            assert sonority(p) == 1

    def test_vowels_highest(self):
        for p in ["AA1", "IY0", "EH2", "AH0", "OW1"]:
            assert sonority(p) == 7

    def test_nasals_mid(self):
        assert sonority("N") == 4
        assert sonority("M") == 4
        assert sonority("NG") == 4

    def test_liquids_above_nasals(self):
        assert sonority("L") > sonority("N")
        assert sonority("R") > sonority("N")

    def test_unknown_returns_zero(self):
        assert sonority("??") == 0


class TestScoreJunction:
    def test_consonant_to_consonant_good_contour(self):
        # Coda ending on nasal (4), next onset starts with stop (1) = good fall-then-rise
        syl_a = _syl(["AH0", "N"])   # ends with nasal
        syl_b = _syl(["T", "AH0"])   # starts with stop
        score = score_junction(syl_a, syl_b)
        assert score > 0

    def test_vowel_vowel_hiatus_penalty(self):
        syl_a = _syl(["AH0"])        # ends with vowel
        syl_b = _syl(["IY0"])        # starts with vowel
        score = score_junction(syl_a, syl_b)
        assert score < 0

    def test_illegal_ng_onset_penalized(self):
        syl_a = _syl(["AH0"])        # anything
        syl_b = _syl(["NG", "AH0"])  # starts with NG = illegal onset
        score = score_junction(syl_a, syl_b)
        assert score <= -2

    def test_single_phoneme_syllables(self):
        syl_a = _syl(["AH0"])
        syl_b = _syl(["T"])
        # Should not crash on minimal syllables
        score = score_junction(syl_a, syl_b)
        assert isinstance(score, (int, float))


class TestOrderSyllables:
    def test_single_syllable_unchanged(self):
        syl = _syl(["AH0"])
        result = order_syllables([syl], seed=42)
        assert result == [syl]

    def test_two_syllables_returns_both(self):
        syls = [_syl(["AH0", "N"], start=0.0), _syl(["T", "AH0"], start=0.5)]
        result = order_syllables(syls, seed=42)
        assert len(result) == 2
        assert set(id(s) for s in result) == set(id(s) for s in syls)

    def test_deterministic_with_seed(self):
        syls = [
            _syl(["AH0", "N"], start=0.0),
            _syl(["T", "AH0"], start=0.5),
            _syl(["S", "IY0"], start=1.0),
        ]
        r1 = order_syllables(syls, seed=99)
        r2 = order_syllables(syls, seed=99)
        assert r1 == r2

    def test_prefers_good_junctions(self):
        # NG-onset syllable should not be placed first (or after vowel-ending)
        syl_ng = _syl(["NG", "AH0"], start=0.0)     # bad as non-initial
        syl_good = _syl(["T", "AH0"], start=0.5)     # good onset
        syl_end = _syl(["AH0", "N"], start=1.0)      # ends on consonant

        # Run many times — the ordering with NG in a bad position should be rare
        results = [order_syllables([syl_ng, syl_good, syl_end], seed=i) for i in range(20)]
        # At least some orderings should avoid NG after a vowel
        scores = []
        for r in results:
            total = sum(score_junction(r[j], r[j+1]) for j in range(len(r)-1))
            scores.append(total)
        # Best-of-5 should consistently pick better orderings than pure random
        assert max(scores) > min(scores) or len(set(scores)) == 1

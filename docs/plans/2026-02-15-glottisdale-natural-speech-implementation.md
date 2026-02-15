# Glottisdale Natural Speech Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Glottisdale output sound like natural (but nonsensical) flowing speech by adding hierarchical prosodic phrasing and phonotactic syllable ordering.

**Architecture:** Replace flat word→gap pipeline with a three-level hierarchy: syllables are grouped into phonotactically-ordered words, words into phrases (no gaps), phrases into sentence groups (with pauses). A new `phonotactics.py` module scores syllable orderings by junction quality. The `process()` function gains new parameters while keeping backward compatibility.

**Tech Stack:** Python, ffmpeg (existing), ARPABET phoneme labels (already in Syllable objects)

**Design doc:** `docs/plans/2026-02-15-glottisdale-natural-speech-design.md`

---

### Task 1: Add phonotactics module with junction scoring

**Files:**
- Create: `glottisdale/src/glottisdale/phonotactics.py`
- Test: `glottisdale/tests/test_phonotactics.py`

**Step 1: Write the failing tests**

Create `glottisdale/tests/test_phonotactics.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_phonotactics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'glottisdale.phonotactics'`

**Step 3: Write the implementation**

Create `glottisdale/src/glottisdale/phonotactics.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_phonotactics.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/phonotactics.py glottisdale/tests/test_phonotactics.py
git commit -m "feat(glottisdale): add phonotactic junction scoring module"
```

---

### Task 2: Add weighted word-length distribution to process()

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py:21-27` (add `_weighted_word_length`)
- Modify: `glottisdale/src/glottisdale/__init__.py:161-169` (replace `randint` with weighted sampling)
- Test: `glottisdale/tests/test_pipeline.py` (add new tests)

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_pipeline.py`:

```python
from glottisdale import _weighted_word_length


class TestWeightedWordLength:
    def test_returns_int_in_range(self):
        rng = __import__("random").Random(42)
        for _ in range(100):
            length = _weighted_word_length(1, 4, rng)
            assert 1 <= length <= 4

    def test_distribution_skews_toward_two(self):
        """With default weights, 2-syllable words should be most common."""
        rng = __import__("random").Random(42)
        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for _ in range(1000):
            length = _weighted_word_length(1, 4, rng)
            counts[length] += 1
        # 2-syllable should be the most common
        assert counts[2] > counts[1]
        assert counts[2] > counts[3]
        assert counts[2] > counts[4]

    def test_single_value_range(self):
        rng = __import__("random").Random(42)
        for _ in range(10):
            assert _weighted_word_length(3, 3, rng) == 3

    def test_range_of_two(self):
        rng = __import__("random").Random(42)
        results = {_weighted_word_length(2, 3, rng) for _ in range(50)}
        assert results == {2, 3}
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py::TestWeightedWordLength -v`
Expected: FAIL — `ImportError: cannot import name '_weighted_word_length'`

**Step 3: Write the implementation**

In `glottisdale/src/glottisdale/__init__.py`, add after the `_parse_gap` function (after line 36):

```python
# Default weights for syllables-per-word: favors 2-syllable words
_WORD_LENGTH_WEIGHTS = [0.30, 0.35, 0.25, 0.10]


def _weighted_word_length(min_syl: int, max_syl: int, rng: random.Random) -> int:
    """Pick a word length using weighted distribution.

    Weights skew toward 2-syllable words for natural-sounding output.
    Falls back to uniform if range doesn't match weight table.
    """
    choices = list(range(min_syl, max_syl + 1))
    if len(choices) == len(_WORD_LENGTH_WEIGHTS):
        return rng.choices(choices, weights=_WORD_LENGTH_WEIGHTS, k=1)[0]
    # Fallback: use truncated/padded weights or uniform
    if len(choices) <= len(_WORD_LENGTH_WEIGHTS):
        weights = _WORD_LENGTH_WEIGHTS[:len(choices)]
        return rng.choices(choices, weights=weights, k=1)[0]
    return rng.randint(min_syl, max_syl)
```

Then modify the word-grouping loop (lines 161-169) to use `_weighted_word_length`:

Replace:
```python
        # Group syllables into variable-length nonsense "words"
        words: list[list[Syllable]] = []
        i = 0
        while i < len(selected):
            word_len = rng.randint(spc_min, spc_max)
            word = selected[i:i + word_len]
            if word:
                words.append(word)
            i += word_len
```

With:
```python
        # Group syllables into variable-length nonsense "words"
        words: list[list[Syllable]] = []
        i = 0
        while i < len(selected):
            word_len = _weighted_word_length(spc_min, spc_max, rng)
            word = selected[i:i + word_len]
            if word:
                words.append(word)
            i += word_len
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py -v`
Expected: All PASS (including existing tests)

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): add weighted word-length distribution"
```

---

### Task 3: Integrate phonotactic ordering into word building

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py:161-169` (add phonotactic reordering after grouping)
- Test: `glottisdale/tests/test_pipeline.py` (add integration-level test)

**Step 1: Write the failing test**

Add to `glottisdale/tests/test_pipeline.py`:

```python
from glottisdale.types import Syllable, Phoneme


def test_word_grouping_uses_phonotactic_ordering():
    """Words with multiple syllables should be phonotactically ordered."""
    from glottisdale import _group_into_words
    import random

    # Create syllables with distinct phoneme patterns
    syls = [
        Syllable([Phoneme("NG", 0.0, 0.1), Phoneme("AH0", 0.1, 0.2)],
                 0.0, 0.2, "test", 0),  # NG onset = bad
        Syllable([Phoneme("T", 0.3, 0.4), Phoneme("AH0", 0.4, 0.5)],
                 0.3, 0.5, "test", 1),  # T onset = good
        Syllable([Phoneme("AH0", 0.6, 0.7), Phoneme("N", 0.7, 0.8)],
                 0.6, 0.8, "test", 2),  # ends on N = good coda
    ]

    rng = random.Random(42)
    words = _group_into_words(syls, spc_min=3, spc_max=3, rng=rng)

    # All 3 syllables should be in one word
    assert len(words) == 1
    assert len(words[0]) == 3
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py::test_word_grouping_uses_phonotactic_ordering -v`
Expected: FAIL — `ImportError: cannot import name '_group_into_words'`

**Step 3: Write the implementation**

Extract the word-grouping logic into a standalone function and integrate phonotactics.

In `glottisdale/src/glottisdale/__init__.py`, add an import at the top:

```python
from glottisdale.phonotactics import order_syllables
```

Add a new function after `_weighted_word_length`:

```python
def _group_into_words(
    syllables: list[Syllable],
    spc_min: int,
    spc_max: int,
    rng: random.Random,
) -> list[list[Syllable]]:
    """Group syllables into variable-length words with phonotactic ordering."""
    words: list[list[Syllable]] = []
    i = 0
    while i < len(syllables):
        word_len = _weighted_word_length(spc_min, spc_max, rng)
        word = syllables[i:i + word_len]
        if word:
            if len(word) > 1:
                word = order_syllables(word, seed=rng.randint(0, 2**31))
            words.append(word)
        i += word_len
    return words
```

Then replace the word-grouping block in `process()` (the block that currently reads `words: list[list[Syllable]] = [] ... i += word_len`) with:

```python
        # Group syllables into phonotactically-ordered nonsense "words"
        words = _group_into_words(selected, spc_min, spc_max, rng)
```

**Step 4: Run all tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): integrate phonotactic ordering into word grouping"
```

---

### Task 4: Add hierarchical phrase/sentence grouping

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py` (add `_group_into_phrases` and `_group_into_sentences`, restructure `process()`)
- Test: `glottisdale/tests/test_pipeline.py`

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_pipeline.py`:

```python
def test_group_into_phrases():
    from glottisdale import _group_into_phrases
    import random

    # 12 words should produce 2-4 phrases with default 3-5 words per phrase
    fake_words = [["w"] for _ in range(12)]  # placeholder word lists
    rng = random.Random(42)
    phrases = _group_into_phrases(fake_words, wpp_min=3, wpp_max=5, rng=rng)

    assert len(phrases) >= 2
    assert len(phrases) <= 6
    # All words accounted for
    total_words = sum(len(p) for p in phrases)
    assert total_words == 12
    # Each phrase has 1-5 words (last phrase may be shorter)
    for phrase in phrases[:-1]:
        assert 3 <= len(phrase) <= 5


def test_group_into_sentences():
    from glottisdale import _group_into_sentences
    import random

    # 6 phrases -> 2-3 sentence groups
    fake_phrases = [["p"] for _ in range(6)]
    rng = random.Random(42)
    sentences = _group_into_sentences(fake_phrases, pps_min=2, pps_max=3, rng=rng)

    assert len(sentences) >= 2
    total_phrases = sum(len(s) for s in sentences)
    assert total_phrases == 6
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py::test_group_into_phrases tests/test_pipeline.py::test_group_into_sentences -v`
Expected: FAIL — `ImportError`

**Step 3: Write the implementation**

Add to `glottisdale/src/glottisdale/__init__.py` after `_group_into_words`:

```python
def _group_into_phrases(
    words: list[list[Syllable]],
    wpp_min: int,
    wpp_max: int,
    rng: random.Random,
) -> list[list[list[Syllable]]]:
    """Group words into phrases of variable length."""
    phrases: list[list[list[Syllable]]] = []
    i = 0
    while i < len(words):
        phrase_len = rng.randint(wpp_min, wpp_max)
        phrase = words[i:i + phrase_len]
        if phrase:
            phrases.append(phrase)
        i += phrase_len
    return phrases


def _group_into_sentences(
    phrases: list,
    pps_min: int,
    pps_max: int,
    rng: random.Random,
) -> list[list]:
    """Group phrases into sentence-level groups."""
    sentences: list[list] = []
    i = 0
    while i < len(phrases):
        sent_len = rng.randint(pps_min, pps_max)
        sentence = phrases[i:i + sent_len]
        if sentence:
            sentences.append(sentence)
        i += sent_len
    return sentences
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): add phrase and sentence grouping functions"
```

---

### Task 5: Restructure process() for hierarchical assembly

This is the core change — replacing the flat word→gap assembly with phrase→sentence assembly.

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py:101-266` (update `process()` signature and assembly logic)
- Test: `glottisdale/tests/test_pipeline.py` (update existing tests for new signature)

**Step 1: Write the failing test**

Add to `glottisdale/tests/test_pipeline.py`:

```python
@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_uses_phrase_grouping(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """Process should use phrase-level grouping with appropriate gaps."""
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    # 20 syllables = enough for multiple words and phrases
    syllables = [
        Syllable([Phoneme("AH0", i * 0.1, (i + 1) * 0.1)],
                 i * 0.1, (i + 1) * 0.1, f"word{i}", i)
        for i in range(20)
    ]

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "test",
        "words": [],
        "syllables": syllables,
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        syllables_per_clip="2-3",
        words_per_phrase="3-4",
        phrases_per_sentence="2-3",
        phrase_pause="400-600",
        sentence_pause="800-1000",
        word_crossfade_ms=25,
        seed=42,
    )

    assert len(result.clips) >= 1
    # concatenate_clips should be called multiple times (once per word, per phrase, final)
    assert mock_concat.call_count >= 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py::test_process_uses_phrase_grouping -v`
Expected: FAIL — `process() got an unexpected keyword argument 'words_per_phrase'`

**Step 3: Write the implementation**

Update the `process()` function signature in `glottisdale/src/glottisdale/__init__.py`. Replace the entire function (lines 101-266) with the new version that:

1. Accepts new parameters: `words_per_phrase`, `phrases_per_sentence`, `phrase_pause`, `sentence_pause`, `word_crossfade_ms`
2. Groups syllables → words → phrases → sentences
3. Assembles audio in two passes: words into phrases (with word crossfade, no gaps), then phrases into final output (with phrase/sentence pauses)

New `process()` signature:

```python
def process(
    input_paths: list[Path],
    output_dir: str | Path = "./glottisdale-output",
    syllables_per_clip: str = "1-4",
    target_duration: float = 10.0,
    crossfade_ms: float = 10,
    padding_ms: float = 25,
    gap: str | None = None,
    words_per_phrase: str = "3-5",
    phrases_per_sentence: str = "2-3",
    phrase_pause: str = "400-700",
    sentence_pause: str = "800-1200",
    word_crossfade_ms: float = 25,
    aligner: str = "default",
    whisper_model: str = "base",
    seed: int | None = None,
) -> Result:
```

The assembly section (currently lines 161-231) becomes:

```python
        # Group syllables into phonotactically-ordered nonsense "words"
        words = _group_into_words(selected, spc_min, spc_max, rng)

        # Build each word: cut individual syllables, fuse them tightly
        clips = []
        word_clip_paths = []
        for word_idx, word_syls in enumerate(words):
            # [existing syllable cutting code unchanged]
            # ...
            clips.append(...)
            word_clip_paths.append(word_output)

        # Group words into phrases, phrases into sentences
        wpp_min, wpp_max = _parse_range(words_per_phrase)
        pps_min, pps_max = _parse_range(phrases_per_sentence)
        pp_min, pp_max = _parse_gap(phrase_pause)
        sp_min, sp_max = _parse_gap(sentence_pause)

        # Map word indices to clip paths for phrase assembly
        # Build phrase WAVs (words concatenated with crossfade, no gaps)
        word_indices = list(range(len(word_clip_paths)))
        word_groups = _group_into_phrases(
            [[i] for i in word_indices], wpp_min, wpp_max, rng
        )

        phrase_paths = []
        for phrase_idx, phrase_word_indices in enumerate(word_groups):
            phrase_clip_paths = [
                word_clip_paths[idx]
                for group in phrase_word_indices
                for idx in group
                if idx < len(word_clip_paths) and word_clip_paths[idx].exists()
            ]
            if not phrase_clip_paths:
                continue
            phrase_path = tmpdir / f"phrase_{phrase_idx:03d}.wav"
            if len(phrase_clip_paths) == 1:
                shutil.copy2(phrase_clip_paths[0], phrase_path)
            else:
                concatenate_clips(
                    phrase_clip_paths, phrase_path,
                    crossfade_ms=word_crossfade_ms,
                )
            phrase_paths.append(phrase_path)

        # Group phrases into sentences, compute gap durations
        sentence_groups = _group_into_sentences(
            list(range(len(phrase_paths))), pps_min, pps_max, rng
        )

        # Build final concatenation with phrase/sentence pauses
        gap_durations = []
        ordered_phrase_paths = []
        for sent_idx, sent_phrase_indices in enumerate(sentence_groups):
            for i, phrase_idx in enumerate(sent_phrase_indices):
                if phrase_idx < len(phrase_paths):
                    ordered_phrase_paths.append(phrase_paths[phrase_idx])
                    # Add gap after this phrase (unless it's the very last phrase)
                    is_last_in_sentence = (i == len(sent_phrase_indices) - 1)
                    is_last_sentence = (sent_idx == len(sentence_groups) - 1)
                    if not (is_last_in_sentence and is_last_sentence):
                        if is_last_in_sentence:
                            # Sentence boundary pause
                            gap_durations.append(rng.uniform(sp_min, sp_max))
                        else:
                            # Phrase boundary pause
                            gap_durations.append(rng.uniform(pp_min, pp_max))

        # Final concatenation
        concatenated_path = output_dir / "concatenated.wav"
        if ordered_phrase_paths:
            concatenate_clips(
                ordered_phrase_paths,
                concatenated_path,
                crossfade_ms=0,
                gap_durations_ms=gap_durations if gap_durations else None,
            )
```

When `gap` is provided (backward compat), use it as `phrase_pause` and set `sentence_pause` to 2x the gap values.

**Step 4: Run all tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: All PASS. May need to fix existing tests that rely on old default behavior.

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): restructure process() for hierarchical phrase assembly"
```

---

### Task 6: Update CLI arguments

**Files:**
- Modify: `glottisdale/src/glottisdale/cli.py:9-55` (add new args, deprecate old ones)
- Modify: `glottisdale/src/glottisdale/cli.py:73-84,127-138` (pass new args to process())
- Test: `glottisdale/tests/test_cli.py` (update + add new tests)

**Step 1: Write the failing tests**

Add to `glottisdale/tests/test_cli.py`:

```python
def test_parse_new_defaults():
    """New prosodic parameters should have correct defaults."""
    args = parse_args([])
    assert args.syllables_per_word == "1-4"
    assert args.words_per_phrase == "3-5"
    assert args.phrases_per_sentence == "2-3"
    assert args.phrase_pause == "400-700"
    assert args.sentence_pause == "800-1200"
    assert args.word_crossfade == 25


def test_parse_new_options():
    args = parse_args([
        "--syllables-per-word", "2-3",
        "--words-per-phrase", "4-6",
        "--phrases-per-sentence", "3-4",
        "--phrase-pause", "300-500",
        "--sentence-pause", "600-900",
        "--word-crossfade", "30",
        "input.mp4",
    ])
    assert args.syllables_per_word == "2-3"
    assert args.words_per_phrase == "4-6"
    assert args.phrases_per_sentence == "3-4"
    assert args.phrase_pause == "300-500"
    assert args.sentence_pause == "600-900"
    assert args.word_crossfade == 30


def test_backward_compat_syllables_per_clip(capsys):
    """--syllables-per-clip should still work as alias."""
    args = parse_args(["--syllables-per-clip", "2-4", "input.mp4"])
    assert args.syllables_per_word == "2-4"


def test_backward_compat_gap(capsys):
    """--gap should still work, mapping to phrase_pause."""
    args = parse_args(["--gap", "100-300", "input.mp4"])
    assert args.phrase_pause == "100-300"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_cli.py::test_parse_new_defaults tests/test_cli.py::test_parse_new_options -v`
Expected: FAIL — `AttributeError: Namespace has no attribute 'syllables_per_word'`

**Step 3: Write the implementation**

Update `cli.py`:

1. Replace `--syllables-per-clip` with `--syllables-per-word` (default `"1-4"`), keep `--syllables-per-clip` as hidden alias
2. Replace `--gap` with `--phrase-pause` (default `"400-700"`), keep `--gap` as hidden alias
3. Add `--words-per-phrase`, `--phrases-per-sentence`, `--sentence-pause`, `--word-crossfade`
4. In `parse_args`, after parsing, handle backward compat: if `--syllables-per-clip` was used, copy to `syllables_per_word`; if `--gap` was used, copy to `phrase_pause`
5. Update both `process()` call sites (local mode and Slack mode) to pass new args

The arg definitions:

```python
    # Core options — prosodic grouping
    parser.add_argument("--syllables-per-word", default="1-4",
                        help="Syllables per word: '3', or '1-4' for variable (default: 1-4)")
    parser.add_argument("--syllables-per-clip", default=None,
                        help=argparse.SUPPRESS)  # deprecated alias
    parser.add_argument("--words-per-phrase", default="3-5",
                        help="Words per phrase: '4', or '3-5' (default: 3-5)")
    parser.add_argument("--phrases-per-sentence", default="2-3",
                        help="Phrases per sentence group: '2', or '2-3' (default: 2-3)")
    parser.add_argument("--phrase-pause", default="400-700",
                        help="Silence between phrases in ms: '500' or '400-700' (default: 400-700)")
    parser.add_argument("--sentence-pause", default="800-1200",
                        help="Silence between sentences in ms: '1000' or '800-1200' (default: 800-1200)")
    parser.add_argument("--word-crossfade", type=float, default=25,
                        help="Crossfade between words in a phrase, ms (default: 25)")
    parser.add_argument("--gap", default=None,
                        help=argparse.SUPPRESS)  # deprecated alias for --phrase-pause
```

After `parser.parse_args(argv)`, add backward compat handling:

```python
    args = parser.parse_args(argv)

    # Backward compat: --syllables-per-clip -> --syllables-per-word
    if args.syllables_per_clip is not None:
        import sys as _sys
        print("Warning: --syllables-per-clip is deprecated, use --syllables-per-word",
              file=_sys.stderr)
        args.syllables_per_word = args.syllables_per_clip
    # Backward compat: --gap -> --phrase-pause
    if args.gap is not None:
        import sys as _sys
        print("Warning: --gap is deprecated, use --phrase-pause", file=_sys.stderr)
        args.phrase_pause = args.gap

    return args
```

Update both `process()` call sites to pass new parameters:

```python
        result = process(
            input_paths=...,
            output_dir=args.output_dir,
            syllables_per_clip=args.syllables_per_word,
            target_duration=args.target_duration,
            crossfade_ms=args.crossfade,
            padding_ms=args.padding,
            words_per_phrase=args.words_per_phrase,
            phrases_per_sentence=args.phrases_per_sentence,
            phrase_pause=args.phrase_pause,
            sentence_pause=args.sentence_pause,
            word_crossfade_ms=args.word_crossfade,
            aligner=args.aligner,
            whisper_model=args.whisper_model,
            seed=args.seed,
        )
```

**Step 4: Update the existing CLI test for new defaults**

The existing `test_parse_defaults` test needs updating since defaults changed. Update it:

```python
def test_parse_defaults():
    args = parse_args([])
    assert args.output_dir == "./glottisdale-output"
    assert args.syllables_per_word == "1-4"
    assert args.target_duration == 10.0
    assert args.crossfade == 10
    assert args.padding == 25
    assert args.phrase_pause == "400-700"
    assert args.sentence_pause == "800-1200"
    assert args.words_per_phrase == "3-5"
    assert args.phrases_per_sentence == "2-3"
    assert args.word_crossfade == 25
    assert args.whisper_model == "base"
    assert args.aligner == "default"
    assert args.seed is None
```

Also update `test_parse_all_options` to use new param names.

**Step 5: Run all tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add glottisdale/src/glottisdale/cli.py glottisdale/tests/test_cli.py
git commit -m "feat(glottisdale): update CLI with prosodic grouping parameters"
```

---

### Task 7: Update integration test

**Files:**
- Modify: `glottisdale/tests/test_integration.py`

**Step 1: Update the integration test**

The existing integration test at `glottisdale/tests/test_integration.py` uses old parameters (`gap="0"`). Update it to use new parameters and verify the hierarchical output structure.

Update the `process()` call in `test_full_pipeline_local_mode`:

```python
    result = process(
        input_paths=[input_wav],
        output_dir=output_dir,
        target_duration=5.0,
        crossfade_ms=0,
        padding_ms=10,
        phrase_pause="0",
        sentence_pause="0",
        word_crossfade_ms=0,
        seed=42,
    )
```

**Step 2: Run integration test**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_integration.py -v -m integration`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: All 35+ tests PASS

**Step 4: Commit**

```bash
git add glottisdale/tests/test_integration.py
git commit -m "test(glottisdale): update integration test for prosodic grouping"
```

---

### Task 8: Update documentation

**Files:**
- Modify: `docs/plans/2026-02-15-glottisdale-design.md` (add note about natural speech changes)

**Step 1: Add a "Superseded by" note to the original design doc**

At the top of `docs/plans/2026-02-15-glottisdale-design.md`, add a note referencing the natural speech design. This is informational only.

**Step 2: Run final full test suite**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add docs/plans/2026-02-15-glottisdale-design.md
git commit -m "docs: cross-reference natural speech design from original design doc"
```

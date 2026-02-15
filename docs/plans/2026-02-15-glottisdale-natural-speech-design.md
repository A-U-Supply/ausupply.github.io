# Glottisdale Natural Speech Design

**Date:** 2026-02-15
**Status:** Approved

## Problem

Glottisdale's syllable collage output sounds like a choppy sequence of isolated syllables rather than flowing, natural-sounding (but nonsensical) speech. Three compounding issues:

1. **Too many monosyllabic "words"** — uniform random 1-5 syllables per word means ~20% are single syllables.
2. **Too choppy** — 200-500ms silence gaps between every word creates dramatic pauses.
3. **No phrase-level rhythm** — flat timing with no sentence-like prosodic structure.

## Goal

Output should sound like someone speaking a language you don't understand — fluid, connected, with natural rhythm and word-like structures — not a robot reading a shuffled list of syllables. Occasional recognizable fragments of the source material are fine (configurable).

## Approach: Prosodic Phrasing + Phonotactic Ordering

Two complementary strategies:

### 1. Hierarchical Grouping (Prosodic Phrasing)

Replace the flat `syllables → words → gaps → output` pipeline with a hierarchical structure:

```
syllables → words → phrases → sentence groups → output
```

**Words** (1-4 syllables, weighted distribution):
- Weights: `[0.30, 0.35, 0.25, 0.10]` for 1/2/3/4 syllables
- 10ms crossfade between syllables within a word (unchanged)

**Phrases** (3-5 words):
- ~25ms crossfade between words within a phrase, no silence gap
- Words flow together like connected speech

**Sentence groups** (2-3 phrases):
- ~400-700ms pause between phrases
- ~800-1200ms pause between sentence groups

### 2. Phonotactic Syllable Ordering

When building a multi-syllable word, score candidate syllable orderings based on junction quality:

**Junction scoring** (between consecutive syllables):
- **Sonority contour:** +1 if sonority falls then rises at the junction (natural coda→onset), -1 if it rises then rises (two onsets smashed together)
- **Illegal onset filter:** -2 if the next syllable starts with an impossible English onset (e.g. /ng/, /tl/, /dl/)
- **Hiatus penalty:** -1 if both syllables have vowels at the junction (vowel-vowel boundary)

**Sonority scale** (ARPABET categories):
- Stops (P, B, T, D, K, G): 1
- Affricates (CH, JH): 2
- Fricatives (F, V, TH, DH, S, Z, SH, ZH, HH): 3
- Nasals (M, N, NG): 4
- Liquids (L, R): 5
- Glides (W, Y): 6
- Vowels (AA, AE, AH, AO, AW, AY, EH, ER, EY, IH, IY, OW, OY, UH, UW): 7

**Ordering strategy:** For each word, try 5 random permutations of its syllables, pick the one with the highest total junction score. Cheap (5 permutations of 2-4 items) and effective.

## Audio Assembly

Two-pass concatenation using existing `concatenate_clips()` and `generate_silence()`:

1. **Pass 1 (per phrase):** Concatenate the phrase's word clips with ~25ms crossfade, no silence gap. Produces one WAV per phrase.
2. **Pass 2 (final):** Concatenate phrase WAVs with silence gaps between them (phrase pauses and sentence pauses).

## CLI Interface

### New Parameters

| Parameter | Default | Description |
|---|---|---|
| `--syllables-per-word` | `"1-4"` (weighted) | Syllables per word, weighted distribution |
| `--words-per-phrase` | `"3-5"` | Words per phrase |
| `--phrases-per-sentence` | `"2-3"` | Phrases per sentence group |
| `--phrase-pause` | `"400-700"` | Silence between phrases (ms) |
| `--sentence-pause` | `"800-1200"` | Silence between sentence groups (ms) |
| `--word-crossfade` | `25` | Crossfade between words in a phrase (ms) |

### Backward Compatibility

| Old Parameter | Maps To | Behavior |
|---|---|---|
| `--syllables-per-clip` | `--syllables-per-word` | Accepted as alias, deprecation warning to stderr |
| `--gap` | `--phrase-pause` | Accepted as alias, deprecation warning to stderr |

### Unchanged Parameters

- `--crossfade` (10ms, intra-word syllable crossfade)
- `--padding` (25ms, syllable cut padding)
- `--target-duration` (10.0s)
- `--whisper-model` (base)
- `--seed`

## GitHub Actions / Slack Bot

No changes needed — unspecified parameters fall back to new CLI defaults automatically.

## Testing

1. Update existing grouping tests for weighted distribution and phrase grouping.
2. New phonotactic tests: junction scoring with known good/bad ARPABET transitions.
3. New phrase assembly tests: verify two-pass concatenation structure.
4. CLI arg tests: new params parse correctly, deprecation warnings fire for old args.

No new test dependencies — phonotactic scoring is pure ARPABET string logic.

## Research Basis

Design informed by speech prosody research:

- **Word length:** ~77% monosyllable in natural English speech (Language Log). We use a skewed distribution favoring 2-syllable words to create flowing output.
- **Pauses:** Natural speech has no silence within phrases, ~400-700ms at phrase boundaries, ~800-1400ms at sentence boundaries (Yamashita et al. 2022, Frontiers in Psychology).
- **Speech rate:** ~4 syllables/second in conversational English (Wikipedia Speech tempo).
- **Prosodic phrasing:** Intonation units are ~4 words / ~1 second, forming a ~1Hz rhythm (Park et al. 2020, Scientific Reports; PNAS 2025).
- **Phonotactics:** English onset/coda constraints well-documented (Sonority Sequencing Principle, Maximum Onset Principle).

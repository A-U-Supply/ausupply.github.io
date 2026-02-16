# Glottisdale Audio Polish — Design Doc

**Date:** 2026-02-15
**Status:** Approved
**Related:** [Glottisdale Design](2026-02-15-glottisdale-design.md), [Natural Speech Design](2026-02-15-glottisdale-natural-speech-design.md)

## Problem

Glottisdale output sounds choppy and artificial. Key issues:
- Dead digital silence between phrases/sentences (zero samples from `anullsrc`)
- Pitch varies wildly between syllables from different sources/moments
- Short crossfades (10-25ms) don't mask timbral differences between sources
- No breath sounds at phrase boundaries (humans breathe)
- Flat amplitude — no natural stress patterns or phrase-final softening

## Approach: Hybrid Analysis/Processing

Use **numpy for analysis** (pitch detection, room tone profiling, energy measurement) and **ffmpeg for audio processing** (cutting, concatenation, mixing). This is additive to the existing pipeline — the battle-tested ffmpeg cut/concat flow stays, it just gets smarter parameters.

numpy is already a transitive dependency via whisper/torch.

## Features

### 1. Continuous Pink Noise Bed

Generate a pink noise floor mixed under the entire output.

- numpy generates a pink noise array matching total output duration
- Mixed with the final concatenated output via ffmpeg `amix` filter as a post-processing step
- Pink noise chosen over white (too hissy) or brown (too rumbly) — pink approximates real room ambience
- Default level: -40dB below speech (very subtle — just eliminates the "void" feeling)

**CLI:** `--noise-level` (dB, default: -40, 0 to disable)

### 2. Room Tone Extraction for Gaps

Replace digital silence in phrase/sentence gaps with actual room tone from source audio.

- After audio extraction, analyze each source with numpy to find quiet segments
- Use RMS energy to identify the quietest 500ms+ region in each source file
- Extract that region as "room tone" for that source
- In gaps between phrases/sentences, use room tone instead of `anullsrc` silence
- Room tone faded in/out at gap boundaries (50ms fade) to prevent pops
- If no quiet region found in any source (all speech, no pauses): fall back to pink noise bed only

**CLI:** `--room-tone / --no-room-tone` (default: enabled)

### 3. Pitch Normalization

Normalize syllable pitches toward a common fundamental frequency so output sounds like one speaker.

- After cutting syllable clips, analyze each with numpy using autocorrelation to estimate F0
- Compute median F0 across all syllables as the target pitch
- Calculate pitch ratio per syllable: `target_f0 / syllable_f0`
- Apply pitch shift via ffmpeg `asetrate` + `aresample` (changes pitch without changing duration)
- Clamp max shift to prevent artifacts (default: ±5 semitones)
- Syllables where pitch detection fails (unvoiced consonants, noise) are left unmodified

**CLI:**
- `--pitch-normalize / --no-pitch-normalize` (default: enabled)
- `--pitch-range` — max semitones of shift allowed (default: 5)

### 4. Longer Crossfades

Increase default crossfade durations to better mask timbral transitions.

- Intra-word crossfade (`--crossfade`): 10ms → **30ms**
- Inter-word crossfade (`--word-crossfade`): 25ms → **50ms**
- No code changes needed — just default value updates
- Existing CLI flags still allow user override

### 5. Breath Sound Extraction

Insert real breath sounds at phrase boundaries, extracted from source audio.

- Scan Whisper word timestamps for inter-word gaps of 200-600ms
- Extract those gap segments from source audio
- Filter by RMS energy: above room tone threshold (not silence), below speech threshold (not a word)
- Pool valid breath candidates per source file
- At phrase boundaries, randomly insert a breath from the pool
- Default probability: 60% per phrase boundary
- If no breaths found in any source: feature silently disabled for that run (no fallback synthesis)
- Breath placed at start of gap, followed by room tone/noise for remainder

**CLI:**
- `--breaths / --no-breaths` (default: enabled)
- `--breath-probability` (default: 0.6)

### 6. Volume Envelope (Prosodic Dynamics)

Apply natural speech volume contour instead of flat amplitude.

**Step 1: RMS Normalization**
- Normalize all syllable clips to a consistent RMS level before assembly
- Prevents random loud/quiet syllables from different sources

**Step 2: Phrase-level envelope**
- Phrase onset: slight ramp up over first word (~+1dB)
- Mid-phrase: relatively flat
- Phrase-final: gentle fade down over last word (~-3dB) — "phrase-final softening"
- Applied via ffmpeg `volume` filter with per-clip gain values

**CLI:**
- `--volume-normalize / --no-volume-normalize` (default: enabled)
- `--prosodic-dynamics / --no-prosodic-dynamics` (default: enabled)

## Pipeline Integration

The features integrate into the existing three-pass concatenation pipeline:

```
Source audio
  │
  ├─ [NEW] Analyze: extract room tone, find breaths (numpy)
  │
  ▼
Whisper transcription → syllable timestamps
  │
  ▼
Cut syllable clips (ffmpeg, existing)
  │
  ├─ [NEW] Measure F0 per clip (numpy autocorrelation)
  ├─ [NEW] Pitch-shift to median F0 (ffmpeg asetrate)
  ├─ [NEW] RMS-normalize clips (ffmpeg volume filter)
  │
  ▼
Pass 1: Syllables → Words (crossfade=30ms, up from 10ms)
  │
  ▼
Pass 2: Words → Phrases (crossfade=50ms, up from 25ms)
  │
  ├─ [NEW] Apply phrase volume envelope (onset boost, final softening)
  │
  ▼
Pass 3: Phrases → Output
  │
  ├─ [NEW] Insert breaths at phrase gaps (if available)
  ├─ [NEW] Fill gaps with room tone (instead of anullsrc silence)
  │
  ▼
[NEW] Post-process: mix pink noise bed under entire output
  │
  ▼
Final output (WAV)
```

## CLI Flag Summary

| Flag | Default | Description |
|------|---------|-------------|
| `--noise-level` | -40 | Pink noise bed level in dB (0 to disable) |
| `--room-tone / --no-room-tone` | enabled | Extract and use room tone for gaps |
| `--pitch-normalize / --no-pitch-normalize` | enabled | Normalize syllable pitches to median F0 |
| `--pitch-range` | 5 | Max pitch shift in semitones |
| `--crossfade` | 30 | Intra-word crossfade in ms (was 10) |
| `--word-crossfade` | 50 | Inter-word crossfade in ms (was 25) |
| `--breaths / --no-breaths` | enabled | Insert extracted breath sounds |
| `--breath-probability` | 0.6 | Chance of breath at each phrase boundary |
| `--volume-normalize / --no-volume-normalize` | enabled | RMS-normalize syllable clips |
| `--prosodic-dynamics / --no-prosodic-dynamics` | enabled | Phrase-level volume envelope |

## Dependencies

No new pip dependencies. numpy is already available via whisper/torch. All audio processing continues to use ffmpeg.

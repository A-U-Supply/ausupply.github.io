# Glottisdale: Time Stretch & Word Repeat Design

**Date:** 2026-02-19

Two new feature families for Glottisdale: time stretching (slowing/speeding individual syllables or the entire output) and word/syllable repetition (duplicating words or stuttering syllables). Both are creative distortion effects, all off by default, applied during the assembly/concatenation stage.

## CLI Flags

### Time Stretch

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--speed` | float | None (off) | Global speed factor. 0.5 = half speed, 2.0 = double speed. Applied to entire output as post-process. |
| `--random-stretch` | float | None (off) | Probability (0-1) that any syllable gets stretched. |
| `--alternating-stretch` | int | None (off) | Stretch every Nth syllable. 2 = every other, 3 = every third. |
| `--boundary-stretch` | int | None (off) | Stretch first and last N syllables of each word. |
| `--word-stretch` | float | None (off) | Probability (0-1) that all syllables in a word get stretched. |
| `--stretch-factor` | str | "2.0" | Stretch amount. Single value (fixed) or range ("1.5-3.0" for random per-syllable). Used by all stretch modes except `--speed`. |

`--speed` is mutually exclusive with the other stretch modes. Multiple non-global stretch modes can be combined — a syllable selected by any active mode gets stretched.

### Word Repeat

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--repeat-weight` | float | None (off) | Probability (0-1) that a word gets repeated. |
| `--repeat-count` | str | "1-2" | Extra copies per repeated word. Single value or range. |
| `--repeat-style` | choice | "exact" | `exact` (duplicate WAV) or `resample` (re-cut new syllables for same word structure). |

### Stutter

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--stutter` | float | None (off) | Probability (0-1) that a syllable gets repeated before word assembly. |
| `--stutter-count` | str | "1-2" | Extra copies of the stuttered syllable. Single value or range. |

Stutter and word repeat are independent, combinable effects.

All flags use the same "single or range" syntax as existing flags (`--syllables-per-word`, `--phrase-pause`, etc.).

## Pipeline Integration

Transforms slot into the existing pipeline using Approach 1 (assembly-stage transforms):

```
 1. Extract audio (existing)
 2. Transcribe + align (existing)
 3. Sample syllables to target duration (existing)
 4. Group syllables into words (existing)
 5. Cut syllable clips (existing)
 6. Pitch normalize syllable clips (existing)
 7. Volume normalize syllable clips (existing)

--- NEW: SYLLABLE TRANSFORMS (step 8) ---
 8a. Stutter: for each word's syllable list, roll dice per syllable.
     If selected, duplicate the clip path in the list N times.
     Duplicates go through normal crossfade in word assembly.
 8b. Syllable stretch: for syllables selected by --random-stretch,
     --alternating-stretch, or --boundary-stretch, run rubberband
     on the individual syllable WAV.

 9. Assemble syllables -> words with crossfade (existing)

--- NEW: WORD TRANSFORMS (step 10) ---
10a. Word stretch: for words selected by --word-stretch, run rubberband
     on the assembled word WAV.

--- NEW: WORD REPEAT (step 11) ---
11.  Word repeat: for each word, roll dice. If selected:
     - exact: duplicate the word Clip entry N times in the list
     - resample: sample new syllables, cut+assemble a new word, insert
     Duplicated/new words get crossfaded in phrase assembly.

12. Assemble words -> phrases with crossfade (existing)
13. Prosodic dynamics (existing)
14. Gap construction (existing)
15. Final concatenation (existing)

--- NEW: GLOBAL SPEED (step 16) ---
16. If --speed is set, run rubberband on the final concatenated WAV.

17. Pink noise mixing (existing)
```

Stutter at step 8a operates on syllable clip lists before word assembly, so duplicates blend with crossfades. Syllable stretch at 8b applies to individual syllable WAVs. Word stretch at 10a applies to assembled word WAVs. Word repeat at 11 duplicates assembled words. Global speed at 16 is a simple post-process.

## Rubberband Integration

Pitch-preserving time stretch via ffmpeg's `rubberband` filter (requires `librubberband-dev`):

```
ffmpeg -i input.wav -af "rubberband=tempo={1/factor}" output.wav
```

A stretch factor of 2.0 means "twice as long" (tempo = 0.5x). Rubberband preserves pitch.

New function in `audio.py`:

```python
def time_stretch_clip(input_path: Path, output_path: Path, factor: float) -> Path:
    """Stretch a clip by factor (2.0 = twice as long). Pitch-preserving via rubberband."""
```

- Factor < 1.0 = speed up (shorter)
- Factor > 1.0 = slow down (longer)
- Factor = 1.0 = no-op (skip)

For `--speed`: inverted — `--speed 0.5` means "play at half speed" = stretch factor 2.0.

Rubberband runs after pitch normalization, so normalized pitch is preserved through the stretch.

## Stretch Selection Logic

When multiple stretch modes are active, a syllable gets stretched if any active mode selects it:

- `--random-stretch P`: `rng.random() < P`
- `--alternating-stretch N`: `syllable_index % N == 0`
- `--boundary-stretch N`: `word_syllable_index < N or word_syllable_index >= word_syllable_count - N`

`--word-stretch` is handled separately at step 10 (whole word WAV).

Stretch factor per selected syllable:
- Single value (`--stretch-factor 2.0`): always 2.0
- Range (`--stretch-factor 1.5-3.0`): `rng.uniform(1.5, 3.0)` per syllable

## Stutter Logic

For each word's syllable list, roll dice per syllable. If selected, duplicate the path in place N times (from `--stutter-count` range). Duplicates go through `concatenate_clips()` with the normal intra-word crossfade.

## Word Repeat Logic

For each word in a phrase's word list, roll dice. If selected:
- `exact`: duplicate the Clip entry N times. Same WAV file read multiple times by ffmpeg.
- `resample`: sample fresh syllables from the pool (matching syllable count), cut, pitch/volume normalize, assemble a new word WAV. Falls back to `exact` if pool is exhausted.

## Error Handling

- **Rubberband not installed:** log warning, skip all stretch operations. Check once at startup.
- **Very short clips:** skip stretch for clips shorter than 80ms (rubberband can fail).
- **Each transform in try/except:** a failed stretch on one syllable doesn't kill the pipeline.
- **Exhausted syllable pool for resample:** fall back to `exact` style.
- **Duration impact:** stretch and repeat increase output length. `--target-duration` controls pre-transform sampling only; final output may be longer. This is expected.

## Testing

- `time_stretch_clip()` — verify output duration is approximately input * factor
- `apply_stutter()` — verify list expansion with known seed
- `apply_word_repeat()` — verify duplication with known seed
- `should_stretch_syllable()` — verify selection logic for each mode
- Stretch factor range parsing (single value, range, invalid input)
- Integration test: full pipeline with stretch + repeat enabled

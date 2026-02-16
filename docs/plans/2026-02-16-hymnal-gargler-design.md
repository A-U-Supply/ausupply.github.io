# Hymnal Gargler — Design

**Date**: 2026-02-16

## Overview

A standalone daily bot (`hymnal-gargler/`) that combines the MIDI bot's melodies from #midieval with Glottisdale's syllable collage pipeline to produce "singing" — nonsensical vocal tracks pitch-mapped to MIDI melodies using rubberband-based pitch shifting and time stretching.

The aesthetic goal is **"drunk choir learns a melody"** — not precise MIDI karaoke, but something that *feels* like singing. Loose pitch following, rhythmic freedom, vibrato on held notes, occasional chorus layering, natural breaths.

## Architecture

```
#sample-sale videos ──→ Glottisdale library (syllabify) ──→ Normalize to median F0
                                                                    │
#midieval MIDI ──→ Parse all 4 tracks ──→ Magenta.js extend to ~40s ─┤
                                                                    ▼
                                                        Vocal Mapper (loose melody following,
                                                        vibrato, chorus, portamento, breaths)
                                                                    │
                                                    ┌───────────────┼───────────────┐
                                                    ▼                               ▼
                                            A cappella track              Full mix (4 MIDI tracks
                                                                          + vocal)
                                                    │                               │
                                                    └───────────┬───────────────────┘
                                                                ▼
                                                    Post to #glottisdale
                                                    (link back to #midieval)
```

## Source Material & Preprocessing

### MIDI source

- Fetch most recent Daily MIDI post from #midieval
- Identify via text pattern: `*Daily MIDI* — <Scale> in <Root> (<Tempo> BPM)`
- Download all 4 MIDI files from thread: melody.mid, drums.mid, bass.mid, chords.mid
- Extract metadata: scale, root, tempo, chords, description, melody instrument, temperature

### Video source

- Fetch 3-5 random videos from #sample-sale (configurable via `--max-videos`, default 5)
- Reuse glottisdale's Slack fetch module (`_download_with_auth()` for redirect handling)

### Syllable preparation

- Run glottisdale pipeline: Whisper transcription → g2p_en → ARPABET syllabification
- Estimate F0 per syllable via autocorrelation
- Normalize all syllables to median F0 using rubberband (uniform "voice" baseline)
- Volume-normalize to median RMS
- Result: a pool of clean, pitch-normalized syllable clips ready for mapping

## Melody Extension (Magenta.js Riffing)

The MIDI melody is 4 bars (~5-15 seconds). Target output is ~40 seconds. Extension uses the same music AI libraries as the MIDI bot — Magenta.js models for melody and drums, programmatic generation for bass and chords.

### Process

- Parse all 4 MIDI files into note sequences
- **Melody extension**: Feed the original melody as a seed to ImprovRNN (same Magenta.js model the MIDI bot uses), generate continuation bars. Use the same scale quantization, temperature controls. Alternate between repeating the original phrase and generating new variations.
- **Drums extension**: Feed the original drum pattern as a seed to DrumsRNN (same as MIDI bot), generate continuation bars with similar style.
- **Bass extension**: Programmatic, derived from chord roots (same 3 pattern types as MIDI bot: root-fifth alternation, walking bass, syncopated). Extend by cycling/varying patterns over the extended chord progression.
- **Chords extension**: Programmatic, loop and vary the chord progression (same voicing approach as MIDI bot). Can repeat the original 4-chord progression or introduce simple substitutions (e.g., relative minor/major swaps).
- All tracks extended to match target duration (~40s)
- Validate: quantize to scale, ensure coherence across all 4 tracks
- Fallback: if Magenta fails, simple loop with octave transpositions
- **Node 18 required** for Magenta.js (same constraint as MIDI bot)

## Vocal Mapping ("Drunk Choir")

The core creative engine. Takes the pool of normalized syllables and the extended melody, produces singing.

### Note-to-syllable assignment

- Walk through extended melody notes sequentially
- For each note, pull the next syllable from the pool (cycle if exhausted)
- **Short notes** (<200ms): one syllable, time-stretched to fit
- **Medium notes** (200ms-1s): one syllable stretched, or 2-3 rapid syllables chanted at same pitch (randomly chosen for variety)
- **Long notes** (>1s): sustained syllable with vibrato, or multi-syllable chant (randomly chosen)

### Pitch mapping (loose, not rigid)

- Target pitch = melody note ± random drift of 0-2 semitones (weighted toward 0)
- **Portamento**: 30-60ms pitch glide between consecutive notes via rubberband interpolation
- **Vibrato**: on notes held >400ms, ±0.5 semitone oscillation at 5-6Hz
- All pitches quantized to the scale after drift (stay in key, just not always on the exact melody note)

### Chorus effect

- On sustained notes (>600ms) and with ~30% probability on other notes
- Layer 2-3 copies of the syllable with ±10-15 cent detuning and 15-30ms time offset
- Mix chorus copies at slightly lower volume than primary voice

### Breathing & phrasing

- Insert natural breath gaps (from glottisdale's breath detection) at rest points in the melody
- Room tone fills gaps instead of digital silence
- Phrase boundaries get 200-400ms pauses

### Time stretching

- All via ffmpeg rubberband filter (formant-preserving)
- Syllable duration adjusted to match note duration
- Rhythmic freedom: some notes ±20% of exact duration for loose, human feel

## Output & Posting

### Audio output (two files)

- **A cappella track**: pitched vocal collage only — mapped, stretched, chorus-layered syllables with breaths and gaps
- **Full mix**: synthesize all 4 extended MIDI tracks (midi-bot's synthesizer, sine-wave approach) mixed under the vocal. Weights: ~0.8 vocal, ~0.5 MIDI backing

### Output format

- WAV internally for processing
- Convert to OGG (64kbps) for Slack upload

### Slack post to #glottisdale

```
🎤 Hymnal Gargler — [Scale] in [Root] ([Tempo] BPM)
_[Description from the MIDI bot post]_

Source: [permalink to #midieval thread]
```

- Full mix OGG uploaded as main message attachment
- A cappella OGG uploaded as threaded reply

### Bot identity

- Posts as "Hymnal Gargler" — distinct from glottisdale bot's posts
- No self-ingestion conflict: glottisdale bot reads from #sample-sale, not #glottisdale; hymnal gargler reads from #midieval + #sample-sale

## CLI

```
hymnal-gargler [--midi melody.mid drums.mid bass.mid chords.mid] [--audio video1.mp4 ...]
```

- **Local mode**: provide `--midi` and `--audio` files directly
- **Slack mode**: omit files, bot fetches from #midieval and #sample-sale (requires `SLACK_BOT_TOKEN`)

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir` | `./hymnal-gargler-output` | Output directory |
| `--max-videos` | 5 | Number of #sample-sale videos to fetch |
| `--target-duration` | 40 | Target output duration in seconds |
| `--whisper-model` | base | Whisper model size |
| `--vibrato / --no-vibrato` | enabled | Vibrato on sustained notes |
| `--chorus / --no-chorus` | enabled | Chorus layering |
| `--drift-range` | 2 | Max semitones of melodic drift |
| `--dry-run` | off | Process but don't post to Slack |
| `--no-post` | off | Local output only, skip Slack |
| `--seed` | random | Seed for reproducibility |
| `--dest-channel` | #glottisdale | Slack channel to post to |

## Schedule

- GitHub Actions workflow, daily ~6pm UTC (11am PT)
- Runs after MIDI bot has posted
- Secrets: `SLACK_BOT_TOKEN`

## Dependencies

**Python:**
- `openai-whisper`, `g2p_en`, `scipy` — via glottisdale library (imported with `importlib.util`)
- `pretty_midi` — MIDI parsing
- `slack-sdk`, `requests` — Slack integration
- `numpy` — audio analysis

**Node.js (for Magenta.js melody/drum extension):**
- **Node 18 required** — Magenta.js incompatible with Node 20+ (same constraint as MIDI bot)
- `@magenta/music` — ImprovRNN (melody) + DrumsRNN (drums)
- `tone` pinned to v14.8.26 (same as MIDI bot)

**System:**
- `ffmpeg` with `librubberband` — pitch shifting, time stretching, mixing

## Codebase Structure

```
hymnal-gargler/
├── bot.py              # Orchestrator (Slack mode entry point)
├── cli.py              # CLI entry point (local + Slack modes)
├── midi_parser.py      # MIDI file parsing, note sequence extraction
├── extend_midi.js      # Magenta.js melody/drum extension (Node 18)
├── extender.py         # Python wrapper for extend_midi.js subprocess
├── vocal_mapper.py     # Note-to-syllable mapping, pitch/time/chorus/vibrato
├── mixer.py            # Mix vocal with MIDI backing tracks
├── slack_fetcher.py    # Fetch MIDI from #midieval, videos from #sample-sale
├── slack_poster.py     # Post results to #glottisdale
└── requirements.txt    # Python dependencies
```

Glottisdale library imported via `importlib.util` (same pattern as puke-box importing midi-bot's synthesizer).

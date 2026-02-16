# Hymnal Gargler Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily bot that pitch-maps Glottisdale syllable collages to MIDI melodies, producing nonsensical "singing" with vibrato, chorus layering, and loose melodic following.

**Architecture:** Standalone `hymnal-gargler/` directory. Fetches MIDI from #midieval and videos from #sample-sale, uses Glottisdale library for syllabification, Magenta.js for melody/drum extension, ffmpeg+rubberband for pitch shifting/time stretching. Posts two tracks (full mix + a cappella) to #glottisdale.

**Tech Stack:** Python 3.11, Node 18 (Magenta.js), ffmpeg with librubberband, pretty_midi, slack-sdk, openai-whisper (via glottisdale)

**Design doc:** `docs/plans/2026-02-16-hymnal-gargler-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `hymnal-gargler/requirements.txt`
- Create: `hymnal-gargler/package.json`
- Create: `hymnal-gargler/__init__.py` (empty)
- Create: `hymnal-gargler/tests/__init__.py` (empty)

**Step 1: Create directory structure**

```bash
mkdir -p hymnal-gargler/tests
```

**Step 2: Create requirements.txt**

```
pretty_midi
slack-sdk>=3.27.0
requests>=2.31.0
numpy
scipy
```

Note: `openai-whisper`, `g2p_en` are installed separately (glottisdale's deps). `torch`/`torchaudio` installed from CPU index in CI.

**Step 3: Create package.json**

```json
{
  "name": "hymnal-gargler",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "@magenta/music": "^1.23.1"
  },
  "overrides": {
    "tone": "14.8.26"
  }
}
```

Same Magenta.js + tone pin as midi-bot.

**Step 4: Create empty __init__.py files**

**Step 5: Commit**

```bash
git add hymnal-gargler/
git commit -m "chore: scaffold hymnal-gargler project"
```

---

### Task 2: MIDI Parser

Parse MIDI files into note sequences. This is the foundation — everything else depends on understanding the MIDI content.

**Files:**
- Create: `hymnal-gargler/midi_parser.py`
- Create: `hymnal-gargler/tests/test_midi_parser.py`

**Context:** Uses `pretty_midi` library. Sample MIDI files available in `puke-box/2026-02-14-161653/` for testing. Each MIDI file has one instrument with notes containing pitch (MIDI number 0-127), start/end times (seconds), and velocity.

**Step 1: Write failing tests**

Test `parse_midi_notes(path) -> list[dict]` — parses a MIDI file into `[{"pitch": int, "start": float, "end": float, "velocity": int}, ...]` sorted by start time.

Test `load_all_tracks(dir) -> dict` — loads all 4 tracks (melody, drums, bass, chords) from a directory, returns `{"melody": [...], "drums": [...], ...}`.

Test `get_track_duration(notes) -> float` — returns max end time, 0 for empty list.

Test `notes_to_sequence_string(notes) -> str` — converts to readable format like `"C4(0.50s) E4(0.50s)"` using `pretty_midi.note_number_to_name()`.

Use `@pytest.mark.skipif` for tests that need real MIDI files from puke-box.

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io && python -m pytest hymnal-gargler/tests/test_midi_parser.py -v`

**Step 3: Write implementation**

Key details:
- `pretty_midi.PrettyMIDI(str(path))` to load MIDI
- Iterate `mid.instruments[*].notes` to extract note data
- Sort by start time
- `pretty_midi.note_number_to_name(pitch)` for human-readable names

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

```bash
git add hymnal-gargler/midi_parser.py hymnal-gargler/tests/test_midi_parser.py
git commit -m "feat(hymnal-gargler): add MIDI parser"
```

---

### Task 3: Melody/Arrangement Extender (Node.js)

Extend all 4 MIDI tracks to ~40 seconds using Magenta.js (ImprovRNN for melody, DrumsRNN for drums) and programmatic looping for bass/chords.

**Files:**
- Create: `hymnal-gargler/extend_midi.js`

**Context:** Same Magenta.js patterns as `midi-bot/generate_midi.js`. Key APIs:
- `new mm.MusicRNN(checkpoint_url)` + `await initialize()` + `continueSequence(seed, steps, temp, chords)`
- `core.midiToSequenceProto(buffer)` to read MIDI files
- `core.sequenceProtoToMidi(sequence)` to write MIDI (requires `controlChanges: []`)
- `core.sequences.quantizeNoteSequence(seq, stepsPerQuarter)` for Magenta input
- ImprovRNN checkpoint: `https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/chord_pitches_improv`
- DrumsRNN checkpoint: `https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/drum_kit_rnn`
- `STEPS_PER_QUARTER = 4` (16th-note resolution)

**Script interface:** Reads JSON params from stdin, writes 4 MIDI files to output directory (CLI arg).

```
echo '{"melody_midi":"/path/to/melody.mid",...}' | node extend_midi.js /output/dir
```

**Params:**
- `melody_midi`, `drums_midi`, `bass_midi`, `chords_midi` — paths to original files
- `scale_intervals` — array of semitone intervals
- `root`, `tempo`, `chords`, `temperature`, `target_bars`

**Extension approach:**
- **Melody**: Read original, use last note as ImprovRNN seed, `continueSequence()` for target_bars, quantize to scale, prepend original melody
- **Drums**: Read original, use last hits as DrumsRNN seed, `continueSequence()`, prepend original
- **Bass**: Loop original with occasional octave transpositions (every 3rd loop: +12, every 4th: -12)
- **Chords**: Straight loop to match target duration
- Each track falls back to file copy if extension fails

**Step 1: Write extend_midi.js**

**Step 2: Install dependencies**

```bash
cd hymnal-gargler && npm install
```

**Step 3: Test with real MIDI files**

```bash
echo '{"melody_midi":"../puke-box/2026-02-14-161653/melody.mid","drums_midi":"../puke-box/2026-02-14-161653/drums.mid","bass_midi":"../puke-box/2026-02-14-161653/bass.mid","chords_midi":"../puke-box/2026-02-14-161653/chords.mid","scale_intervals":[0,1,5,7,8],"root":"E","tempo":120,"chords":["Em7","G7","Am7","Dmaj7"],"temperature":1.0,"target_bars":20}' | node extend_midi.js /tmp/hymnal-test-extend
```

Verify output with:
```bash
python3 -c "import pretty_midi; [print(f'{n}: {sum(len(i.notes) for i in pretty_midi.PrettyMIDI(f\"/tmp/hymnal-test-extend/{n}.mid\").instruments)} notes') for n in ['melody','drums','bass','chords']]"
```

**Step 4: Commit**

```bash
git add hymnal-gargler/extend_midi.js hymnal-gargler/package.json
git commit -m "feat(hymnal-gargler): add Magenta.js MIDI extension"
```

---

### Task 4: Python Wrapper for MIDI Extension

Python module that calls extend_midi.js as a subprocess (same pattern as midi-bot/bot.py).

**Files:**
- Create: `hymnal-gargler/extender.py`
- Create: `hymnal-gargler/tests/test_extender.py`

**Context:** The midi-bot calls Node.js via `subprocess.run(["node", script, output_dir], input=json.dumps(params), capture_output=True, text=True, timeout=300, cwd=script_dir)`.

**Key functions:**
- `_build_extension_params(midi_dir, scale_intervals, root, tempo, chords, temperature, target_duration) -> dict` — calculates `target_bars` from `target_duration` and `tempo` (bars = duration * tempo / 240)
- `extend_tracks(midi_dir, output_dir, ...) -> bool` — calls Node.js subprocess, returns True/False

**Step 1: Write failing tests** — test `_build_extension_params` returns correct target_bars, test structure

**Step 2: Run tests to verify they fail**

**Step 3: Write implementation**

**Step 4: Run tests** — unit tests should pass; optionally run integration test with Node 18

**Step 5: Commit**

```bash
git add hymnal-gargler/extender.py hymnal-gargler/tests/test_extender.py
git commit -m "feat(hymnal-gargler): add Python wrapper for MIDI extension"
```

---

### Task 5: Syllable Preparation

Extract syllables from audio using the glottisdale library, normalize them to a uniform pitch and volume.

**Files:**
- Create: `hymnal-gargler/syllable_prep.py`
- Create: `hymnal-gargler/tests/test_syllable_prep.py`

**Context:** Import glottisdale modules via `importlib.util` from `../glottisdale/src/glottisdale/`. Key modules: `audio` (extract_audio, cut_clip), `transcribe` (Whisper ASR), `syllabify` (syllabify_words → list[Syllable]), `analysis` (estimate_f0, compute_rms, read_wav), `types` (Syllable, Phoneme dataclasses).

**Data type:**
```python
@dataclass
class SyllableClip:
    path: Path           # WAV file
    f0: float | None     # fundamental frequency Hz
    rms: float           # volume level
    duration: float      # seconds
    phonemes: list[str]  # ARPABET labels
    word: str            # parent word
```

**Key functions:**
- `_import_glottisdale() -> dict` — cached import of glottisdale modules via importlib
- `extract_syllables(input_paths, output_dir, whisper_model) -> list[SyllableClip]` — full pipeline: extract_audio → transcribe → syllabify_words → cut_clip each syllable → estimate F0/RMS
- `normalize_pitch(clip_paths, output_dir, max_shift=5.0) -> list[dict]` — estimate F0 per clip, compute median, pitch-shift each to median using rubberband (`ffmpeg -filter:a "rubberband=pitch=RATIO"`)

**Step 1: Write failing tests** — test import, test normalization reduces F0 variance (use clips from `glottisdale-2026-02-15-clips.zip`)

**Step 2: Run tests to verify they fail**

**Step 3: Write implementation**

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add hymnal-gargler/syllable_prep.py hymnal-gargler/tests/test_syllable_prep.py
git commit -m "feat(hymnal-gargler): add syllable extraction and pitch normalization"
```

---

### Task 6: Vocal Mapper — Core Engine

The creative heart: maps normalized syllables to melody notes with pitch shifting, time stretching, vibrato, chorus, portamento, and rhythmic freedom.

**Files:**
- Create: `hymnal-gargler/vocal_mapper.py`
- Create: `hymnal-gargler/tests/test_vocal_mapper.py`

**Key functions:**

`calculate_pitch_shift(source_f0, target_midi_note, drift_range=0, seed=None) -> float`
- Converts MIDI note to Hz via `pretty_midi.note_number_to_hz()`
- Base shift = `12 * log2(target_hz / source_f0)`
- Adds triangular random drift weighted toward 0

`should_add_chorus(note_duration, rng) -> bool`
- Always True for >0.6s notes, 30% chance otherwise

`get_vibrato_params(note_duration) -> dict | None`
- Returns `{"rate_hz": 4.5-6.5, "depth_semitones": 0.3-0.6}` for notes >0.4s, None otherwise

`assign_syllables_to_notes(clips, notes, drift_range, seed) -> list[dict]`
- Walks melody notes, cycles through voiced syllable clips
- Short notes (<200ms): single syllable, time-stretched
- Medium notes (200ms-1s): sustain or occasional 2-syllable chant (30% chance)
- Long notes (>1s): sustain with vibrato, or 2-4 syllable chant (50% chance)
- ±20% duration jitter for rhythmic freedom
- Returns `[{"note": dict, "clips": list, "pitch_shift": float, "target_duration": float, "vibrato": dict|None, "chorus": bool, "type": "sustain"|"chant"}, ...]`

`render_assignment(assignment, output_path, sample_rate=16000) -> Path | None`
- Chant type: process each clip, concatenate with 20ms crossfade
- Sustain type: process single clip
- Processing: rubberband filter for pitch+time (`rubberband=pitch=RATIO:tempo=RATIO`)
- Vibrato: ffmpeg `vibrato=f=RATE:d=DEPTH` filter
- Chorus: 2 detuned copies (±12 cents) with 15-25ms delay, mixed at 0.4 weight via `amix`

`render_vocal_track(assignments, output_dir, crossfade_ms=30) -> Path | None`
- Renders all assignments, concatenates with crossfade
- Returns path to `vocal_acappella.wav`

**Step 1: Write failing tests** — test pitch shift calculation, assignment logic, vibrato/chorus decisions

**Step 2: Run tests to verify they fail**

**Step 3: Write implementation**

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add hymnal-gargler/vocal_mapper.py hymnal-gargler/tests/test_vocal_mapper.py
git commit -m "feat(hymnal-gargler): add vocal mapper — the drunk choir engine"
```

---

### Task 7: Audio Mixer

Mix the a cappella vocal track with synthesized MIDI backing tracks.

**Files:**
- Create: `hymnal-gargler/mixer.py`
- Create: `hymnal-gargler/tests/test_mixer.py`

**Context:** Reuses `midi-bot/src/synthesizer.py` via importlib (same pattern as puke-box). The synthesizer's `synthesize_preview(midi_dir, output_path) -> bool` loads 4 MIDI files, mixes them at 22050Hz, writes WAV.

**Key functions:**
- `_import_synthesizer()` — importlib from `../midi-bot/src/synthesizer.py`
- `synthesize_backing(midi_dir, output_path) -> Path | None` — calls synthesizer
- `mix_vocal_with_backing(vocal, backing, output, vocal_weight=0.8, backing_weight=0.5) -> Path | None` — ffmpeg `amix` with `stream_loop -1` on backing, `duration=shortest`
- `convert_to_ogg(wav, ogg, bitrate="64k") -> Path | None` — ffmpeg WAV→OGG

**Step 1: Write failing tests** — test synthesize_backing with real MIDIs, test mix with sine wave WAVs

**Step 2: Run tests to verify they fail**

**Step 3: Write implementation**

**Step 4: Run tests**

**Step 5: Commit**

```bash
git add hymnal-gargler/mixer.py hymnal-gargler/tests/test_mixer.py
git commit -m "feat(hymnal-gargler): add audio mixer for vocal + MIDI backing"
```

---

### Task 8: Slack Integration (Fetcher + Poster)

Fetch MIDI from #midieval and post results to #glottisdale.

**Files:**
- Create: `hymnal-gargler/slack_fetcher.py`
- Create: `hymnal-gargler/slack_poster.py`
- Create: `hymnal-gargler/tests/test_slack_fetcher.py`
- Create: `hymnal-gargler/tests/test_slack_poster.py`

**Context:**
- `parse_midi_message(text)` — same regex as puke-box: `r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)'`
- `_download_with_auth(url, token)` — manual redirect following (5 max), preserves Bearer auth
- `find_channel_id(client, name)` — cursor-based pagination through `conversations_list`
- `fetch_latest_midi(token, channel)` — finds most recent MIDI bot post, downloads 4 MIDIs from thread, validates with `b'MThd'` magic bytes. Returns `{"metadata": dict, "midi_dir": Path, "permalink": str}`
- `fetch_videos(token, channel, max_videos, download_dir)` — delegates to glottisdale's `fetch.py` via importlib
- Poster: `files_upload_v2` for uploads, get thread_ts from `files_info` shares metadata, retry with exponential backoff

**Slack post format:**
```
:microphone: *Hymnal Gargler* — [Scale] in [Root] ([Tempo] BPM)
_[Description]_

Source: <permalink|Daily MIDI>
```
Full mix as main message, a cappella as threaded reply.

**Step 1: Write failing tests** — test parse_midi_message with various formats

**Step 2-5: Implement and commit**

```bash
git add hymnal-gargler/slack_fetcher.py hymnal-gargler/slack_poster.py hymnal-gargler/tests/
git commit -m "feat(hymnal-gargler): add Slack fetcher and poster"
```

---

### Task 9: CLI

Command-line interface with local mode and Slack mode.

**Files:**
- Create: `hymnal-gargler/cli.py`
- Create: `hymnal-gargler/tests/test_cli.py`

**Context:** Same pattern as `glottisdale/src/glottisdale/cli.py`. Local mode when `--midi` and `--audio` provided, Slack mode otherwise (requires `SLACK_BOT_TOKEN` env).

**Flags:**
| Flag | Default | Description |
|------|---------|-------------|
| `--midi` | None | MIDI files (local mode) |
| `--audio` | None | Audio/video files (local mode) |
| `--output-dir` | `./hymnal-gargler-output` | Output directory |
| `--target-duration` | 40 | Seconds |
| `--max-videos` | 5 | #sample-sale videos |
| `--whisper-model` | base | tiny/base/small/medium |
| `--vibrato / --no-vibrato` | enabled | |
| `--chorus / --no-chorus` | enabled | |
| `--drift-range` | 2 | Semitones |
| `--dry-run` | off | No Slack post |
| `--no-post` | off | Local only |
| `--seed` | random | |
| `--source-channel` | #midieval | |
| `--video-channel` | #sample-sale | |
| `--dest-channel` | #glottisdale | |

**Local mode pipeline:** load_all_tracks → extract_syllables → normalize_pitch → assign_syllables_to_notes → render_vocal_track → synthesize_backing → mix → convert_to_ogg

**Slack mode pipeline:** fetch_latest_midi → extend_tracks → fetch_videos → (same as local from extract onward) → post_results

**Step 1: Write failing tests** — test parse_args with various flag combinations

**Step 2-5: Implement and commit**

```bash
git add hymnal-gargler/cli.py hymnal-gargler/tests/test_cli.py
git commit -m "feat(hymnal-gargler): add CLI with local and Slack modes"
```

---

### Task 10: Bot Entry Point

Simple orchestrator for GitHub Actions.

**Files:**
- Create: `hymnal-gargler/bot.py`

**Pattern:** Same as `glottisdale/bot.py` — adds parent dirs and glottisdale slack module to sys.path, delegates to `cli.main()`.

**Step 1: Write bot.py**

**Step 2: Test with --help**

```bash
python hymnal-gargler/bot.py --help
```

**Step 3: Commit**

```bash
git add hymnal-gargler/bot.py
git commit -m "feat(hymnal-gargler): add bot entry point"
```

---

### Task 11: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/hymnal-gargler.yml`

**Schedule:** Daily 11pm UTC (3pm PT). Also `workflow_dispatch` with inputs for target_duration, max_videos, whisper_model, seed, dry_run.

**Steps:**
1. checkout
2. setup-python 3.11
3. setup-node 18 (cache npm, hymnal-gargler/package-lock.json)
4. cache whisper+torch models
5. `apt-get install ffmpeg librubberband-dev`
6. Install Python deps: torch CPU, requirements.txt, `pip install -e glottisdale/`, NLTK data
7. `cd hymnal-gargler && npm ci`
8. Run `python hymnal-gargler/bot.py $ARGS` with `SLACK_BOT_TOKEN` secret

**Step 1: Write workflow YAML**

**Step 2: Validate syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/hymnal-gargler.yml'))"
```

**Step 3: Commit**

```bash
git add .github/workflows/hymnal-gargler.yml
git commit -m "ci: add Hymnal Gargler daily workflow"
```

---

### Task 12: Integration Test — End-to-End Local Mode

Run the full pipeline locally with real MIDI files and existing glottisdale clips.

**Files:**
- Create: `hymnal-gargler/tests/test_integration.py`

**Test:** Load MIDI from puke-box, create SyllableClips from glottisdale-2026-02-15-clips.zip (skip Whisper for speed), normalize pitch, assign to first 6 melody notes, render vocal, synthesize backing, mix, convert to OGG. Assert all output files exist and have reasonable sizes.

Mark with `@pytest.mark.slow` and `@pytest.mark.skipif` for missing test data.

**Step 1: Write integration test**

**Step 2: Run**

```bash
python -m pytest hymnal-gargler/tests/test_integration.py -v --timeout=120
```

**Step 3: Commit**

```bash
git add hymnal-gargler/tests/test_integration.py
git commit -m "test(hymnal-gargler): add end-to-end integration test"
```

---

### Task 13: Documentation & Memory Update

**Step 1: Update MEMORY.md** with Hymnal Gargler section (key conventions, architecture, gotchas like Node 18 requirement, rubberband dependency)

**Step 2: Verify all tests pass**

```bash
python -m pytest hymnal-gargler/tests/ -v
```

**Step 3: Final commit**

```bash
git add -A hymnal-gargler/ docs/plans/
git commit -m "docs: finalize hymnal-gargler implementation"
```

---

## Dependency Graph

```
Task 1 (scaffold) ─→ Task 2 (MIDI parser) ─→ Task 3 (extend_midi.js) ─→ Task 4 (extender.py)
                  │                                                              │
                  ├→ Task 5 (syllable prep) ─────────────────────────────────────┤
                  │                                                              │
                  ├→ Task 8 (Slack fetch/post) ──────────────────────────────────┤
                                                                                 │
                                                                                 ▼
                                                                 Task 6 (vocal mapper) ─→ Task 7 (mixer)
                                                                                                │
                                                                                                ▼
                                                                                 Task 9 (CLI) ─→ Task 10 (bot.py)
                                                                                                     │
                                                                                                     ▼
                                                                                         Task 11 (workflow)
                                                                                                     │
                                                                                                     ▼
                                                                                     Task 12 (integration test)
                                                                                                     │
                                                                                                     ▼
                                                                                         Task 13 (docs)
```

Tasks 2, 5, and 8 can be parallelized after Task 1.

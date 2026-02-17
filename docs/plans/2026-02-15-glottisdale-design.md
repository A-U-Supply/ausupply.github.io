# Glottisdale — Syllable-Level Audio Collage Tool

**Date:** 2026-02-15

> **Note:** This design was extended by the [Natural Speech Design](2026-02-15-glottisdale-natural-speech-design.md), which adds hierarchical prosodic phrasing and phonotactic syllable ordering to make output sound like natural flowing speech.

> **Note:** ForceAlign was dropped after implementation — its phoneme timestamps are fake (word duration / phoneme count), identical to g2p_en proportional timing. The pipeline uses Whisper word timestamps + g2p_en + syllabify instead. The abstract aligner interface (`align.py`) is retained for future BFA integration.

## Overview

A Python tool that pulls video/audio from a Slack channel (or local files), segments speech into syllables using ASR + forced alignment, cuts individual audio clips at syllable boundaries, randomly shuffles them, and concatenates the result into an audio collage. Posts the output to a different Slack channel or writes to disk.

Designed as a standalone library + CLI that also runs in GitHub Actions.

## Pipeline

```
Input file(s) (video/audio, local or from Slack)
  │
  ├─ ffprobe → detect video vs audio
  ├─ ffmpeg → extract 16kHz mono WAV (skip if already audio)
  ├─ Whisper ASR → transcript + word-level timestamps
  ├─ ForceAlign → ARPABET phoneme-level timestamps
  ├─ Syllabifier → syllable boundaries (Maximum Onset Principle)
  ├─ Group syllables (--syllables-per-clip)
  ├─ Apply ±25ms padding, clamp to file bounds
  ├─ ffmpeg → cut individual OGG clips with 10ms afade
  ├─ Sample across sources (round-robin for variety, up to --target-duration)
  ├─ Random shuffle → concatenate with configurable crossfade + random gaps
  └─ Output: clips/, concatenated.ogg, manifest.json, clips.zip
```

## Package Structure

```
glottisdale/
  pyproject.toml                # Package metadata, [slack] extras
  src/
    glottisdale/
      __init__.py               # Public API: process()
      cli.py                    # argparse CLI entrypoint
      transcribe.py             # Whisper ASR → transcript
      align.py                  # Abstract aligner interface + ForceAlign backend
      syllabify.py              # Phoneme sequence → syllable boundaries
      audio.py                  # ffmpeg: extract, cut, concatenate, convert
      types.py                  # Dataclasses: Phoneme, Syllable, Clip, Result
      syllabify_arpabet.py      # Vendored from kylebgorman/syllabify
  slack/
    glottisdale_slack/
      __init__.py
      fetch.py                  # Pull videos from Slack channel
      post.py                   # Post results to Slack channel
  bot.py                        # GH Actions entrypoint (imports both)
  requirements.txt              # Pinned deps for GH Actions
```

- `src/glottisdale/` is the pure library — zero Slack dependency
- `slack/glottisdale_slack/` is optional, installed via `pip install glottisdale[slack]`
- `bot.py` ties them together for GH Actions
- PEX-packageable: all pure Python except ffmpeg (system dep) and torch (binary wheels)

## Public API

```python
from glottisdale import process

result = process(
    input_paths=["speech.mp4"],
    output_dir="./clips",
    syllables_per_clip=1,
    target_duration=10.0,
    crossfade_ms=10,
    padding_ms=25,
    gap="50-200",
    aligner="forcealign",
    whisper_model="base",
    seed=None,
)
# result.clips: list[Clip]
# result.concatenated: Path
# result.transcript: str
# result.manifest: dict
```

## Data Types

```python
@dataclass
class Phoneme:
    label: str          # ARPABET (e.g. "AH0") or IPA if BFA
    start: float        # seconds
    end: float

@dataclass
class Syllable:
    phonemes: list[Phoneme]
    start: float
    end: float
    word: str           # parent word
    word_index: int     # position in transcript

@dataclass
class Clip:
    syllables: list[Syllable]
    start: float        # with padding applied
    end: float
    source: str         # input filename
    output_path: Path

@dataclass
class Result:
    clips: list[Clip]
    concatenated: Path
    transcript: str
    manifest: dict
```

## Aligner Interface

> **Architecture change (during implementation planning):** ForceAlign was dropped after discovering its phoneme timestamps are evenly divided across the word duration (not truly force-aligned). The default backend uses Whisper word timestamps + g2p_en + vendored syllabify instead, which produces identical phoneme timing with fewer dependencies. The aligner interface is retained for future BFA integration.

```python
class Aligner(ABC):
    @abstractmethod
    def process(self, audio_path: Path) -> dict:
        """Transcribe and align audio, returning syllable-level timestamps."""

class DefaultAligner(Aligner):
    """Whisper ASR + g2p_en + ARPABET syllabifier."""

class BFABackend(Aligner):
    """IPA phonemes via Bournemouth Forced Aligner. Future."""
```

**DefaultAligner** (implemented backend):
- Whisper word-level timestamps + g2p_en for ARPABET phoneme conversion
- Vendored syllabifier splits phonemes into syllables
- Proportional timing distributes word duration across syllables by phoneme count
- No additional model downloads beyond Whisper

~~**ForceAlign** (dropped):~~
- ~~pip installable: `pip install forcealign`~~
- ~~ARPABET output works directly with vendored syllabifier~~
- ~~Wav2Vec2 model (~360MB), cached in `~/.cache/torch/`~~
- ~~CPU-only, no special config~~
- **Dropped:** phoneme timestamps are fake (word duration / phoneme count), identical to what g2p_en + proportional timing produces without the extra dependency

**BFA** (future backend):
- Bournemouth Forced Aligner, v1.1.0 (Feb 2026) — very new
- IPA output, 240x faster than MFA, pip installable + `espeak-ng`
- Would need IPA-based syllabification (sonority sequencing) or IPA→ARPABET mapping

Both backends return `list[Phoneme]`; syllabifier detects label format and applies appropriate rules.

### Syllabification

- Vendored from `kylebgorman/syllabify` — single-file ARPABET syllabifier
- Uses Maximum Onset Principle: vowel nuclei mark syllable centers, preceding consonants assigned to following syllable's onset if they form a valid English onset cluster
- Syllable boundaries respect word boundaries — no cross-word syllabification (linguistically imperfect but avoids weird clips spanning word gaps)

### Why not other aligners?

| Tool | Phoneme-level? | pip install? | CI-friendly? | Verdict |
|------|---------------|-------------|-------------|---------|
| ForceAlign | Yes (ARPABET) | Yes | Excellent | **v1 choice** |
| BFA | Yes (IPA) | Yes (+espeak-ng) | Good | **Future v2** |
| WhisperX | No (ortho chars) | Yes (fragile) | Poor (heavy deps) | Rejected |
| stable-ts | No (word-level) | Yes | Good | Wrong granularity |
| MFA | Yes (phones) | No (conda) | Poor | Rejected |
| whisper-timestamped | No (word-level) | Yes | Good | Wrong granularity |
| NeMo | Token-level | Yes (huge) | Poor | Way too heavy |

## Audio Processing

All ffmpeg interaction in `audio.py`.

### Extract audio
```bash
ffmpeg -i input.mp4 -vn -ar 16000 -ac 1 -f wav temp_audio.wav
```
16kHz mono WAV (Whisper's native format). Skip if input is already audio (detected via ffprobe).

### Cut syllable clips
```bash
ffmpeg -ss {start - padding} -i audio.wav -t {duration + 2*padding} \
  -af "afade=t=in:d=0.01:curve=hsin,afade=t=out:st={dur-0.01}:d=0.01:curve=hsin" \
  -c:a libvorbis -q:a 4 \
  clip.ogg
```
- 25ms padding default (configurable), clamped to file bounds
- 10ms half-sine fades prevent clicks at cut points
- libvorbis quality 4 (~128kbps)
- Audio-only cutting is sample-accurate — no keyframe issues

### Concatenate with gaps
The concatenation step interleaves clips with randomly-sized silent gaps:

1. For each pair of adjacent clips, generate a silence segment of random duration within the `--gap` range
2. Build a concat list: `clip1.ogg`, `silence_73ms.ogg`, `clip2.ogg`, `silence_142ms.ogg`, ...
3. Silence segments generated via ffmpeg: `ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 0.073 -c:a libvorbis silence.ogg`

**No crossfade + no gaps:** Pure concat demuxer with stream copy (fastest).

**With crossfade:** Chain `acrossfade` filters between clips (after silence insertion). For 50+ clips, write filter chain to temp file and use `-filter_complex_script`.

**Gap generation is seeded** — same `--seed` produces same gap durations for reproducibility.

### Coarticulation & padding
- 25ms padding each side preserves onset/offset coarticulation
- 10ms half-sine fades eliminate audio discontinuities
- Syllable boundaries at word edges avoid unnatural cross-word cuts
- Based on PSOLA/concatenative synthesis research: 1-2 pitch periods (~8-16ms for male, ~5-10ms for female) is sufficient overlap

## CLI Interface

```
glottisdale [OPTIONS] [INPUT_FILES...]
```

### Core options

| Flag | Default | Description |
|------|---------|-------------|
| `INPUT_FILES...` | — | Local video/audio files. If omitted, fetches from Slack. |
| `--output-dir` | `./glottisdale-output` | Where clips + concatenated file go |
| `--syllables-per-clip` | `1` | Group N syllables per clip |
| `--target-duration` | `10.0` | Target total duration in seconds |
| `--crossfade` | `10` | Crossfade between clips in ms (0 = hard cut) |
| `--padding` | `25` | Padding around each syllable cut in ms |
| `--gap` | `50-200` | Random silence between clips in ms (see below) |
| `--whisper-model` | `base` | Whisper model size (tiny/base/small) |
| `--aligner` | `forcealign` | Alignment backend |
| `--seed` | random | RNG seed for reproducible output |

### Gap syntax

The `--gap` flag controls silence inserted between clips in the concatenated output:
- `--gap 0` — no gaps, syllables butt together (one continuous alien word)
- `--gap 100` — fixed 100ms silence between every clip
- `--gap 50-200` — uniform random between 50-200ms per gap (default)

Combined with `--crossfade`, full control over rhythm:
- `--gap 0 --crossfade 0` → one continuous alien word
- `--gap 50-200 --crossfade 10` → natural-ish speech rhythm with variety
- `--gap 500-2000 --crossfade 0` → dramatic pauses, words emerging from silence

### Slack options (only when no INPUT_FILES)

| Flag | Default | Description |
|------|---------|-------------|
| `--source-channel` | `#sample-sale` | Slack channel to pull videos from |
| `--dest-channel` | `#glottisdale` | Slack channel to post results to |
| `--max-videos` | `5` | Max source videos to sample from |
| `--dry-run` | `false` | Process but don't post to Slack |
| `--no-post` | `false` | Skip posting, just write to output-dir |

### Modes

- **Local mode** (`glottisdale video1.mp4 video2.mp4`): No Slack at all. Write to `--output-dir`, print provenance to stdout.
- **Slack mode** (`glottisdale` with no files): Fetch from `--source-channel`, post to `--dest-channel`.
- **Hybrid** (`glottisdale --no-post`): Fetch from Slack, write locally only.

### Output structure
```
glottisdale-output/
  clips/
    001_video1_w03_s02.ogg    # clip 001, from "video1", word 3, syllable 2
    002_othervid_w11_s01.ogg
    ...
  concatenated.ogg
  clips.zip
  manifest.json
```

### Stdout
```
Processed 3 source files, extracted 47 syllables
Sources:
  - video1.mp4 (22 syllables) https://slack.com/archives/C123/p456
  - video2.mp4 (15 syllables)
  - video3.mp4 (10 syllables) https://slack.com/archives/C123/p789
Selected 38 syllables for ~10.2s target duration
Output:
  clips/001_video1_w03_s02.ogg ... clips/038_video3_w07_s01.ogg
  concatenated.ogg (10.2s)
  clips.zip
```

## Slack Integration

### Fetching videos from #sample-sale

Uses existing codebase patterns:
- `conversations_list` with cursor pagination to resolve channel name → ID
- `conversations_history` with `limit=200` + cursor pagination to fetch messages
- Filter for messages with `files` where `mimetype` starts with `video/`
- `_download_with_auth()` pattern (manual redirect following) to download `url_private_download`
- Content-Type validation to reject non-video responses

**Rate limits:** Slack API tier 3 methods (conversations.history) allow ~50 req/min. With `limit=200`, even a channel with 10k messages needs only 50 requests. No custom rate limiting logic needed.

**Video filtering:** Slack file objects include `mimetype` (e.g. `video/mp4`, `video/quicktime`). Filter on `mimetype.startswith("video/")`.

### Posting to #glottisdale

- `chat_postMessage` to post summary text → get `thread_ts` and `channel_id`
- `files_upload_v2` for concatenated.ogg (main thread)
- `files_upload_v2` for clips.zip (threaded reply)
- Include source message permalinks in the summary text
- Requires `channel_id` (not name) for `files_upload_v2` — resolved from `chat_postMessage` response

**Slack app scopes needed:** `channels:history`, `channels:read`, `files:read`, `files:write`, `chat:write`

### No state tracking

Each run randomly samples from all available videos in the channel. No state.json, no tracking of previously processed videos. Truly random selection means repetition is unlikely to produce identical output.

## GitHub Actions

### Workflow

```yaml
name: Glottisdale
on:
  schedule:
    - cron: '0 18 * * *'  # 10am PT daily
  workflow_dispatch:
    inputs:
      target_duration:
        description: 'Target duration in seconds'
        default: '10'
      max_videos:
        description: 'Max source videos'
        default: '5'
      whisper_model:
        description: 'Whisper model (tiny/base/small)'
        default: 'base'

jobs:
  glottisdale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache Whisper + ForceAlign models
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/whisper
            ~/.cache/torch
          key: glottisdale-models-${{ inputs.whisper_model || 'base' }}

      - name: Install system dependencies
        run: sudo apt-get install -y ffmpeg

      - name: Install Python dependencies
        run: |
          pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
          pip install -r glottisdale/requirements.txt

      - name: Run glottisdale
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        run: >
          python glottisdale/bot.py
          --target-duration ${{ inputs.target_duration || '10' }}
          --max-videos ${{ inputs.max_videos || '5' }}
          --whisper-model ${{ inputs.whisper_model || 'base' }}
```

### Model caching

- Whisper models cache to `~/.cache/whisper/` (~140MB for base, ~460MB for small)
- ForceAlign/Wav2Vec2 models cache to `~/.cache/torch/hub/` (~360MB)
- `actions/cache@v4` keyed on model name — only re-downloads when `--whisper-model` changes
- Total cache: ~500MB for base model combo, well within GH Actions 10GB limit

### No git commits

Unlike the other bots, glottisdale doesn't commit anything back to the repo. Output goes to Slack only. The workflow is stateless.

## Dependencies

### Core library (no Slack)
```
openai-whisper       # ASR
forcealign           # Phoneme-level alignment
torch                # Required by both (CPU-only wheel)
torchaudio           # Required by forcealign
```
System: `ffmpeg`

### Slack extras
```
slack-sdk            # Slack API client
requests             # File downloads
```

### CI install strategy
```bash
# CPU-only torch (saves ~1.5GB vs CUDA wheels)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install openai-whisper forcealign slack-sdk requests
```

### PEX packaging
- `pyproject.toml` with `[project.scripts]` entry: `glottisdale = "glottisdale.cli:main"`
- PEX can bundle everything except ffmpeg (system dep)
- torch is the heaviest dependency (~800MB CPU wheel) — PEX will be large but functional
- Alternative: ship as a Docker image with ffmpeg baked in for portable deployment

## pyproject.toml sketch

```toml
[project]
name = "glottisdale"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "openai-whisper",
    "forcealign",
    "torch",
    "torchaudio",
]

[project.optional-dependencies]
slack = ["slack-sdk>=3.27.0", "requests>=2.31.0"]

[project.scripts]
glottisdale = "glottisdale.cli:main"
```

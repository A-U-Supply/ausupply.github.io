# Song Title Integration Design

**Date:** 2026-03-13
**Status:** Draft

## Overview

Use song titles from the #song-titles Slack channel as a creative seed across the generation pipeline: the midi-bot uses the title to drive musical parameter selection via LLM, glottisdale-bot uses it for deterministic seeding and as a label, and hymnal-bot inherits the title from the Daily MIDI message naturally.

A new `song-titles-bot/` scrapes #song-titles daily, filters messages via HF Inference API, stores titles with metadata in JSON, and regenerates the interactive `this-song-is-a-junkyard.html` page.

## Components

### 1. `song-titles-bot/` — Scraper + Page Generator

#### Directory Structure

```
song-titles-bot/
├── bot.py                  # Orchestrator: scrape → filter → save → generate HTML
├── src/
│   ├── slack_scraper.py    # Fetch messages from #song-titles (cursor pagination)
│   ├── filter.py           # HF Inference API classification (is this a song title?)
│   ├── html_generator.py   # Regenerate this-song-is-a-junkyard.html from JSON
│   └── config.py           # Config loading
├── config.yaml             # Channel, model, thresholds
├── titles.json             # Canonical song titles database
└── templates/
    └── junkyard.html.j2    # Jinja2 template for the interactive page
```

#### Data Model — `titles.json`

```json
[
  {
    "id": "msg-1710000000.000001",
    "title": "Tip of the Fatberg",
    "date": "2026-01-15",
    "author_id": "U12345678",
    "permalink": "https://slack.com/archives/C.../p..."
  }
]
```

- `id` is the Slack message timestamp (unique, stable)
- Scraper tracks the latest `id` seen so it only processes new messages on each run
- Existing titles from `slack-song-generator/cache/titles.json` (139 titles) will be migrated with synthetic IDs and no author/permalink metadata

#### Filtering

- Uses HF Inference API (Llama-3.3-70B-Instruct), same as midi-bot — replaces the local Ollama dependency from the old `slack-song-generator`
- Simple classification prompt: "Is this message a song title or just conversation? Respond YES or NO."
- Batch messages to minimize API calls
- Free tier is sufficient — only a handful of new messages per day

#### HTML Generation

- Jinja2 template reproduces the full interactivity from current `this-song-is-a-junkyard.html`:
  - Draggable divs with random positioning, rotation, font size, color
  - Full mouse + touch support (drag, pinch-resize, two-finger rotate)
  - localStorage persistence
  - Toolbar controls (color, size, rotate, animation, background)
  - Shared header (cheeze-bourger2.png + h1)
  - vcfmw.css + inline style overrides
- Titles sourced from `titles.json` instead of being hardcoded

#### Cleanup

- Remove `songtitles.html`
- Remove `slack-song-generator/` directory (logic absorbed into new bot)

### 2. midi-bot Changes — Prompt & Config

#### Configuration

New fields in `config.yaml`:

```yaml
seed_source: "song-titles"  # "song-titles" or "headlines" (default: song-titles)
song_titles_path: "../song-titles-bot/titles.json"  # resolved relative to script dir (Path(__file__).parent)
```

When `seed_source: "song-titles"`:
- Load titles.json, read `midi-bot/used-song-titles.json`, pick random unused title, record usage
- When pool exhausted, reset the used list
- If `titles.json` is missing or empty, log a warning and fall back to headlines mode
- Headlines are **not scraped** — skip entirely
- Inspirations still sampled (2 random, as now)

When `seed_source: "headlines"`:
- Existing behavior unchanged (backward compatible)

#### Usage Tracking — `used-song-titles.json`

```json
{"used_ids": ["msg-1710000000.000001", "msg-1710000002.000003"]}
```

This file **must be committed to git** by the CI workflow (alongside any other changes), otherwise usage tracking resets on every fresh checkout. Same applies to `glottisdale-bot/used-song-titles.json`.

#### New Prompt Template

Stored as `midi-bot/prompt_template_song_title.txt`. Uses the same `---` separator convention as the existing template (system prompt above, user prompt below):

```
You are a composer with severe internet brain rot. You select unusual musical parameters inspired by a song title and strange imagery.
---
The song title below is your primary creative seed. Let it drive your
choices — the mood, tempo, scale, and instruments should all feel like
they belong to a song with this name.

SONG TITLE:
"{title}"

Musical inspiration for today:
{inspirations}

TODAY'S SCALE OPTIONS (pick ONE — use the exact name):
{scales}

MELODY INSTRUMENTS:
{melody_instruments}

CHORD INSTRUMENTS:
{chord_instruments}

Output a JSON object with these exact keys:
- "scale": You MUST choose one of the numbered scales above. Copy the name EXACTLY.
- "root": a root note (e.g. "C", "F#", "Bb") — vary this, don't always pick C or A
- "chords": an array of exactly 4 chord symbols that work with the chosen scale
- "tempo": a number between 40 and 200 (let the song title guide the energy)
- "temperature": a number between 0.5 and 1.5 (how wild the AI-generated melody and drums should be)
- "melody_instrument": a MIDI program number from the MELODY INSTRUMENTS list above
- "chord_instrument": a MIDI program number from the CHORD INSTRUMENTS list above
- "description": a single weird sentence inspired by the song title (with 1-3 emojis, Slack formatting allowed)

Output ONLY the JSON. No explanation. No markdown code fence.
```

#### Generator Changes

`generate_music_params()` in `src/generator.py` currently requires `headlines: list[str]`. Refactor to:
- Accept an optional `song_title: str` parameter (mutually exclusive with `headlines`)
- When `song_title` is provided, load `prompt_template_song_title.txt` and use `build_llm_prompt_from_title()` which formats `{title}`, `{inspirations}`, `{scales}`, `{melody_instruments}`, `{chord_instruments}`
- When `headlines` is provided, existing `build_llm_prompt()` and `prompt_template.txt` are used unchanged
- `bot.py` orchestrator selects the code path based on `config["seed_source"]`

#### Existing Prompt Update

Update the existing headlines prompt to replace "surrealist" with non-cliché language:
- System: "You are a composer with severe internet brain rot..."
- Description field: "a single weird sentence inspired by the headlines"

#### Slack Message Format

Song title in bold as the first line:

```
*"Tip of the Fatberg"*
:musical_note: *Daily MIDI* — Maqam Hijaz in F (110 BPM)
_sewage rises in quarter-tones, the fatberg hums its anthem 🫠🎵_

:musical_keyboard: Melody — ImprovRNN, Tenor Sax (MIDI 66), temperature 1.2
:drum_with_drumsticks: Drums — DrumsRNN, temperature 1.2
:guitar: Bass — Programmatic from chord roots
:musical_score: Chords — Fm7  Bbm7  Cm7b5  Dbm6
```

The `params` dict gets a new `song_title` field passed through from selection.

### 3. glottisdale-bot Changes

#### Title Selection

- Load `song-titles-bot/titles.json`, read `glottisdale-bot/used-song-titles.json`, pick random unused, record usage
- Same selection/tracking logic as midi-bot (duplicated, ~15 lines — not worth a shared dependency)

#### Deterministic Seed

Hash the title string into an integer seed:

```python
import hashlib
seed = int(hashlib.sha256(title.encode()).hexdigest()[:8], 16)
```

Pass as `--seed {seed}` to `glottisdale collage` CLI. Currently seed is `None` (random). If an explicit `--seed` is provided via workflow dispatch, it takes precedence over the song-title-derived seed.

#### Slack Message Format

```
*"Tip of the Fatberg"*
:scissors: *Glottisdale* — 47 words from 3 source(s)
```

Title in bold as first line, same pattern as midi-bot.

#### No Changes To

- Rust glottisdale library
- Video fetching
- Audio processing / Whisper transcription / clip selection

### 4. hymnal-bot — Minor Parser Tweak

The hymnal-bot parses the Daily MIDI message via `parse_midi_message()` in `slack_fetcher.py`. The existing regex uses `re.search()` (not `re.match()`), so it already scans the full message text and should find `*Daily MIDI*` on line 2 without changes. The description regex `r'_(.+?)_'` matches italic text — since the song title uses bold `*"..."*` not italic, it should not interfere.

**Edge case:** if a song title contains underscores, the description regex could match incorrectly. Add a guard to skip matches that appear before the `*Daily MIDI*` line.

The song title line can be extracted via a new regex `r'^\*"(.+?)"\*'` and included in the hymnal Slack post as the first line (same bold format as midi-bot and glottisdale-bot).

### 5. GitHub Actions & Scheduling

#### New Workflow — `.github/workflows/song-titles.yml`

- Trigger: daily cron (5am UTC) + `workflow_dispatch`
- Steps: checkout → Python setup → pip install (slack-sdk, requests, jinja2, huggingface-hub) → run bot.py → commit changes (titles.json, this-song-is-a-junkyard.html)
- Secrets: `SLACK_BOT_TOKEN`, `HF_TOKEN` (matches existing midi-bot convention)
- Commit message: `chore: update song titles (YYYY-MM-DD) [skip ci]`

#### Scheduling Order (UTC)

1. **song-titles.yml** — 5am (scrape + filter + regenerate HTML)
2. **daily-midi.yml** — existing schedule (after song-titles)
3. **glottisdale.yml** — existing schedule (after song-titles)
4. **hymnal-gargler.yml** — existing schedule (after daily-midi)
5. **puke-box.yml** — 10pm (unchanged)

Consuming bots don't strictly depend on song-titles running first — if titles.json hasn't changed they pick from the existing pool. Scheduling it earlier ensures new titles are available same-day.

## What Stays the Same

- Rust glottisdale library — untouched
- MIDI generation (Node.js/Magenta.js) — untouched
- Inspirations (midi-bot) — still sampled, complement the song title
- puke-box — unchanged, scrapes from #midieval as before
- drawma — unrelated, unchanged

## Migration

1. Migrate 139 existing titles from `slack-song-generator/cache/titles.json` into `song-titles-bot/titles.json` with synthetic IDs (no date/author/permalink metadata for legacy titles)
2. Remove `slack-song-generator/` directory
3. Remove `songtitles.html`

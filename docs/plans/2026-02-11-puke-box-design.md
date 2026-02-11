# Puke Box — Design Doc

**Date:** 2026-02-11

## Overview

A 90s geocities/myspace-inspired jukebox page (`puke-box.html`) that plays audio previews of the daily MIDI bot's output and lets visitors download MIDI files. A separate GitHub Action scrapes #midieval from Slack, downloads MIDI files, synthesizes OGG previews, and commits everything to the repo.

## Architecture

```
Slack #midieval (source of truth)
         |
         v
[Puke-box scraper action] — daily, after midi bot runs
   - Scrape channel history for "Daily MIDI" messages
   - Parse metadata from message text
   - Download 4 MIDI files from threaded replies
   - Synthesize preview.ogg from MIDIs (sine waves + noise burst drums)
   - Commit to puke-box/YYYY-MM-DD/ + update manifest.json
         |
         v
puke-box.html — static page, reads manifest.json at runtime
```

The midi bot stays unchanged. Slack is the source of truth. The repo is a cache.

## Page Design

### Visual Concept

Standalone page (no shared header, no vcfmw.css). The jukebox stock photo (`img/puke-box.jpg`) is the centerpiece, scaled large and centered. All interactive elements are overlaid on top of the image using absolute positioning within a relative container, aligned to the jukebox's physical zones.

### Geocities Chaos Elements

- Tiled background pattern (music-themed or garish 90s texture)
- Cursor trails following the mouse
- Random blinking text scattered around ("NOW PLAYING", "HOT TRACKS", "COOL TUNEZ")
- `<marquee>` tags with jukebox-themed text scrolling in various directions
- Comic Sans and system fonts
- Clashing neon color palette: green, hot pink, cyan, yellow
- Fake visitor counter at the bottom
- Unhinged but jukebox-themed — not explicitly referencing geocities

### Jukebox Interactive Zones

Three zones mapped onto the jukebox image:

**1. Top display window (amber/yellow panel) — Marquee**
- Scrolling text showing the current track's surreal LLM description
- Updates when a new track is selected

**2. Middle lattice area (diamond grid) — Card Flipper**
- Shows one song at a time
- Up/down arrows styled as physical jukebox buttons to flip through
- Each card displays:
  - Date (retro format: "FEB•11•2026")
  - Scale + root + tempo ("Maqam Nahawand in Bb — 95 BPM")
  - First ~50 chars of surreal description as teaser
- Click card or "SELECT" button to load track
- Keyboard arrows for navigation
- Wraps around (last → first)
- URL hash updates with date (`#2026-02-11`) for deep linking

**3. Bottom control panel (small display + buttons) — Player & Downloads**
- Play/pause button (chunky 90s beveled style)
- Simple progress bar
- Track info: scale name, root, tempo
- "GET MIDI" — downloads zip of 4 .mid files
- "GET PREVIEW" — downloads the .ogg directly

### Audio Behavior

- HTML5 `<audio>` element playing OGG
- Selecting a new track swaps src and auto-plays
- Track does not auto-advance when finished (jukebox style: you pick your song)
- Page loads on most recent track, auto-plays it

### Mobile

- Jukebox image + overlays scale down proportionally
- Touch swipe up/down for flipper navigation
- Touch-friendly button sizes

## Data Structure

```
puke-box/
  manifest.json              ← array of all entries, newest first
  2026-02-11/
    preview.ogg              ← ~30KB, synthesized from MIDIs
    melody.mid               ← ~500 bytes
    drums.mid
    bass.mid
    chords.mid
    meta.json                ← full params from midi bot
```

### manifest.json

Lightweight array for the page to fetch on load:

```json
[
  {
    "date": "2026-02-11",
    "description": "A restless Tuesday in a bureaucracy that runs on reverb",
    "scale": "Maqam Nahawand",
    "root": "Bb",
    "tempo": 95
  }
]
```

### meta.json (per entry)

Full params — loaded on demand when a track is selected:

```json
{
  "scale": "Maqam Nahawand",
  "root": "Bb",
  "tempo": 95,
  "temperature": 1.2,
  "chords": ["Bbm", "Ebm7", "Ab7", "Dbmaj7"],
  "melody_instrument": 73,
  "chord_instrument": 6,
  "description": "A restless Tuesday in a bureaucracy that runs on reverb"
}
```

## Scraper Action

### Script: `puke-box/scrape_midieval.py`

1. Read #midieval channel history via Slack API
2. Find messages matching "Daily MIDI" pattern
3. For each message:
   - Parse date from message timestamp
   - Skip if `puke-box/YYYY-MM-DD/` already exists (no duplicates)
   - Parse metadata from message text (scale, root, tempo, instruments, description)
   - Download 4 MIDI files from threaded file uploads
   - Synthesize preview.ogg from MIDIs using existing `synthesizer.py` + ffmpeg WAV→OGG
   - Write meta.json
4. Regenerate manifest.json from all date directories
5. Commit + push

### Workflow: `.github/workflows/puke-box.yml`

- **Schedule:** Daily, offset from midi bot (e.g. 2 hours after)
- **Manual trigger:** `workflow_dispatch`
- **Dependencies:** Python 3.11, ffmpeg (pre-installed on ubuntu-latest), pretty_midi, scipy, slack-sdk
- **Secrets:** `SLACK_BOT_TOKEN`

### Reuse

- Reuses `midi-bot/src/synthesizer.py` for OGG generation (synthesize MIDI → WAV, then ffmpeg → OGG)
- Same Slack scraping pattern as drawma scraper

## Storage Estimates

- Per day: ~30KB OGG + ~2KB MIDI files + ~1KB meta.json = ~33KB
- Per year: ~12MB
- Pruning: not needed for foreseeable future, can address if it grows

## Homepage Link

Draggable `img/puke-box.jpg` (resized thumbnail) on index.html, linking to puke-box.html.

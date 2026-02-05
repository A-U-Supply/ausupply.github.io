# Drawma Gallery - Design Doc

**Status:** Implemented

## Overview

A daily GitHub Action scrapes drawings from the `#drawma` Slack channel, downloads them to the repo, and maintains a manifest. A standalone HTML page displays the art as a dark, one-at-a-time slideshow in a 90s Twin Peaks / David Lynch aesthetic.

## Goals

- Automatically collect drawings posted in response to daily surreal prompts
- Present them in a focused, atmospheric gallery experience
- Run daily with no manual intervention

## Architecture

### Components

1. **Image scraper** (`surreal-prompt-bot/scrape_gallery.py`) — Uses Slack API to fetch images from `#drawma`, downloads new ones, updates manifest
2. **Gallery page** (`drawma.html`) — Standalone dark slideshow, reads manifest, one image at a time
3. **GitHub Action** (`.github/workflows/scrape-drawma.yml`) — Runs daily, commits new images

### Data Flow

```
Slack #drawma --> scrape_gallery.py --> img/drawma/*.jpg + manifest.json --> drawma.html
```

## Image Scraper

### Script: `surreal-prompt-bot/scrape_gallery.py`

Standalone Python script using `slack-sdk`.

### How It Works

1. Calls `conversations.history` to get recent messages from `#drawma`
2. Checks each message for `files` attachments with `image/*` mimetype
3. Calls `conversations.replies` on bot prompt messages to catch threaded drawings
4. For each new image not already in the manifest, downloads via `url_private_download` (using bot token for auth)
5. Saves to `img/drawma/{date}-{slack_file_id}.{ext}`
6. Updates `img/drawma/manifest.json`

### Associating Drawings with Prompts

The scraper identifies bot messages (by bot user ID) as prompts. Images in that message's thread or posted the same day are associated with that prompt. Not perfect but good enough — manifest can be hand-edited if needed.

### Manifest Entry Structure

```json
{
  "id": "F07ABC123",
  "filename": "2026-02-03-F07ABC123.jpg",
  "date": "2026-02-03",
  "prompt": "Local Fish Achieves Enlightenment Through Fiscal Policy",
  "artist": "jake",
  "width": 800,
  "height": 600
}
```

### Slack Bot Scopes Required

Current scopes: `chat:write`

Additional scopes needed (one-time setup):
- `channels:history` — read messages from `#drawma`
- `files:read` — download image files

## Gallery Page

### File: `drawma.html`

Standalone page at project root. No shared header — fully self-contained dark page.

### Visual Design — Twin Peaks 90s Aesthetic

- Black background with dark red (`#8b0000`) accents (the Red Room)
- Chevron/zig-zag floor pattern as subtle CSS background along the bottom edge
- Serif font (Georgia or similar) — white/cream text, slightly glowing
- Image centered and large, thin red border or soft vignette
- Navigation: click left/right halves of screen, or arrow keys
- Prompt text fades in below image on hover/click — italics, like a whispered secret
- Page title with subtle flicker animation — uneasy, not obnoxious
- Slow fade/dissolve transitions between images

### Behavior

- Loads `img/drawma/manifest.json` on page load
- Shows images newest-first
- Left/right keyboard arrow navigation
- Subtle image counter: "7 / 42"
- Preloads adjacent images for smooth transitions
- No draggable content — focused viewing experience
- No audio

## GitHub Action

### Workflow: `.github/workflows/scrape-drawma.yml`

- **Schedule:** Daily at 11pm PT (7am UTC) — end of day, gives people time to post drawings
- **Trigger:** Also supports `workflow_dispatch` for manual runs
- **Secrets:** `SLACK_BOT_TOKEN` (already configured)
- **Commits directly to master** — same pattern as `generate-history.yml`
- **Commit message:** `chore: add drawma gallery images (YYYY-MM-DD)`
- **No empty commits** — skips if no new images found

### Steps

1. Checkout repo
2. Set up Python, install slack-sdk + requests
3. Run `scrape_gallery.py`
4. If new images exist, commit and push `img/drawma/` + manifest
5. If no new images, exit cleanly

## File Structure

```
img/drawma/
  manifest.json
  2026-02-03-F07ABC123.jpg
  2026-02-03-F07ABC456.png
  ...
drawma.html
surreal-prompt-bot/scrape_gallery.py
.github/workflows/scrape-drawma.yml
```

## One-Time Setup

1. Add `channels:history` and `files:read` scopes to the Slack app
2. Reinstall app to workspace (Slack requires this after scope changes)
3. Create `img/drawma/` directory

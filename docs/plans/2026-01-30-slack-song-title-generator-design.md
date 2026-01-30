# Slack Song Title Generator - Design Doc

## Overview

A Python CLI tool that fetches song titles from a Slack channel and generates a chaotic, geocities-style HTML page for ausupply.github.io.

## Goals

- Pull song title ideas from a Slack channel
- Filter out discussion/noise using local LLM (Ollama)
- Generate visually chaotic HTML with randomized layouts
- Highly configurable with argparse options
- Reusable pattern for other content types in the future

## Architecture

### Components

1. **Slack Fetcher** - Pulls messages from a channel via Slack API
2. **Song Title Filter** - Uses Ollama to classify messages as song titles or not
3. **Chaos Generator** - Transforms titles into scattered, randomized HTML

### Tech Stack

- Python 3.11+
- `slack-sdk` - Slack API client
- `requests` - HTTP calls to Ollama
- `jinja2` - HTML templating
- `uv` - Dependency management

## Slack Integration

### One-Time Setup

1. Go to https://api.slack.com/apps
2. Create New App → From Scratch
3. Name it (e.g., "Song Title Fetcher"), select workspace
4. Go to OAuth & Permissions
5. Add Bot Token Scopes:
   - `channels:history` (read messages)
   - `channels:read` (list channels)
6. Install to Workspace
7. Copy the Bot User OAuth Token (`xoxb-...`)
8. Invite the bot to your channel: `/invite @YourBotName`
9. Get channel ID (right-click channel → View channel details → copy ID)

### Environment Variables

```
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL_ID=C0XXXXXXX
```

### Fetching Logic

- Pull messages from channel (configurable limit, default 500)
- Extract text content only
- Ignore bot messages, system events, reactions-only messages
- Cache results for quick regeneration

## LLM Filtering (Ollama)

### Requirements

- Ollama installed and running locally
- A model like `llama3` or `mistral` pulled

### Classification Prompt

```
Is this message a potential song title for a band?
Not discussion about titles - the title itself.
Reply only YES or NO.

Message: "{message_text}"
```

### Filtering Rules

- YES: "Dust Bobbles", "Even Sky Is Blue", "Flaming Lips Don't Use Jelly"
- NO: "yo that one's great", "we should use this", "@jake check this"

## HTML Generation

### Visual Style

Chaotic scatter collage inspired by:
- Geocities pages
- Strange artist/gallery websites
- Weird net art

### Randomized Properties (per title)

- **Position**: Absolute positioning, random x/y across viewport
- **Rotation**: -30° to +30° (configurable)
- **Font size**: Small to large range
- **Color**: Neon palette (hot pink, lime, cyan, yellow, red, etc.)
- **Font family**: Mix of Comic Sans, Courier, Arial, Times
- **Effects**: text-shadow, occasional blink, dotted borders

### Page Elements

- No grid, no order - pure chaos
- Optional tiled background
- Optional scattered images/GIFs from media directory
- Small header somewhere

## CLI Interface

```
usage: generate-song-page.py [options]

Options:
  --channel-id ID      Slack channel (overrides .env)
  --output PATH        Output HTML file path
  --seed INT           Random seed for reproducible chaos
  --media-dir PATH     Directory of images/GIFs to scatter
  --density 1-10       How packed/sparse the layout is
  --color-palette NAME Preset: neon, pastel, mono, random
  --font-chaos 1-5     How many different fonts to use
  --max-rotation DEG   Maximum rotation in degrees (default 30)
  --effects LIST       Enable: blink, shadows, borders
  --title-limit INT    Max titles to display
  --fetch-only         Fetch & filter only, don't generate HTML
  --generate-only      Skip fetch, use cached titles
  --random             Randomize all visual settings
```

### Examples

```bash
# Basic generation
./generate-song-page.py --output ../ausupply.github.io/songtitles.html

# Pure chaos mode
./generate-song-page.py --random --output ../ausupply.github.io/songtitles.html

# Reproducible chaos
./generate-song-page.py --random --seed 42 --output ../ausupply.github.io/songtitles.html

# With media
./generate-song-page.py --media-dir ./gifs --output ../ausupply.github.io/songtitles.html

# Just update the cache
./generate-song-page.py --fetch-only

# Regenerate from cache (no Slack call)
./generate-song-page.py --generate-only --random
```

## Project Structure

```
slack-song-generator/
├── pyproject.toml
├── .env                 # SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
├── .env.example
├── README.md            # Setup instructions
├── src/
│   ├── __init__.py
│   ├── cli.py           # argparse entrypoint
│   ├── slack_fetcher.py # Slack API logic
│   ├── filter.py        # Ollama classification
│   ├── generator.py     # HTML chaos generator
│   └── templates/
│       └── chaos.html.j2  # Jinja2 base template
└── cache/
    └── titles.json      # Cached filtered titles
```

## Workflow

### First Time Setup

```bash
cd slack-song-generator
cp .env.example .env
# Edit .env with Slack token + channel ID
uv sync
```

### Generate a Page

```bash
./generate-song-page.py --output ../ausupply.github.io/songtitles.html
# Preview, commit, push
```

### Regenerate with Different Chaos

```bash
./generate-song-page.py --random --output ../ausupply.github.io/songtitles.html
```

## Error Handling

- Clear error if Slack token invalid or channel not found
- Warning if Ollama isn't running (with instructions)
- Graceful handling if media directory empty or missing
- Validation of all CLI arguments

## Future Extensions

- Support for other Slack channels/content types
- Additional visual themes/presets
- Interactive mode for manual title curation
- RSS/feed integration as alternative source

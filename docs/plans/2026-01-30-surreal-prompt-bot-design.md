# Surreal Prompt Bot - Design Doc

## Overview

A Python script that runs daily via GitHub Actions at 7am PT. It scrapes headlines from diverse news sources, picks random artistic inspirations from a text file, feeds both to Groq's free Llama API, and posts a surreal headline-style drawing prompt (with emojis) to the `#drawma` Slack channel.

## Goals

- Generate daily surrealist drawing prompts inspired by political/financial news
- Post automatically to Slack without relying on local machine
- Completely free (Groq free tier + GitHub Actions)
- Configurable via YAML config and CLI options

## Architecture

### Components

1. **News Scraper** - Pulls headlines from ~8 news sites using BeautifulSoup
2. **Inspiration Sampler** - Picks random lines from inspirations.txt
3. **Prompt Generator** - Sends headlines + inspirations to Groq API
4. **Slack Poster** - Posts the generated prompt to #drawma
5. **Config System** - YAML config file + CLI overrides via argparse
6. **GitHub Action** - Cron trigger at 7am PT daily

### Data Flow

```
News Sites ─┬─► Headlines ──┬──► Groq LLM ──► Surreal Prompt ──► Slack
            │               │
inspirations.txt ──► Sample ┘
```

### Tech Stack

- Python 3.11+
- `requests` + `beautifulsoup4` - Web scraping
- `groq` - Groq API client (free tier)
- `slack-sdk` - Slack posting
- `pyyaml` - Config parsing
- GitHub Actions - Scheduling

## News Scraping

### Target Sources (diverse spectrum)

- Financial Times
- Fox News
- CNN
- Reuters
- BBC News
- Bloomberg
- The Guardian
- Breitbart

### How It Works

- Each source has a scraper function that fetches homepage and extracts 3-5 top headlines
- Uses `requests` + `BeautifulSoup` (no browser needed)
- If a source fails (site changed, down), logs warning and continues
- Collects ~20-30 headlines total, picks random subset of ~10 for LLM

### Fragility Note

Web scraping breaks when sites redesign. When it does, update the selector for that source. Bot still works if some sources fail - only needs a few headlines.

## Inspiration File

### File: `inspirations.txt`

Simple text file, one inspiration per line:

```
corporate memphis art style
1990s clip art energy
deep fried meme aesthetic
renaissance painting but wrong
vaporwave capitalism
classified government document
children's educational poster
infomercial accident
liminal space vibes
wikihow illustration gone wrong
stock photo nightmare
```

### How It Works

- Bot picks 1-3 random lines from the file
- Feeds them to LLM alongside news headlines
- Adds variety and artistic direction

## Prompt Generation

### LLM Setup

- Groq free tier with `llama-3.1-8b-instant`
- Single API call per day (well within free limits)

### The Prompt

```
You are a surrealist artist with severe internet brain rot.

Today's news headlines:
{headlines}

Artistic inspiration for today:
{inspirations}

Generate a single drawing prompt in the style of a surreal,
unhinged headline. Include 1-3 emojis. One sentence.
Do not explain it.
```

### Example Outputs

- "📉 Local Fish Achieves Enlightenment Through Fiscal Policy, Refuses Comment 🐟"
- "🏛️ The Moon Files For Bankruptcy While Clouds Hold Emergency Session 💨"
- "Breaking: Your Childhood Bedroom Now A Subsidiary Of Feelings Inc. 🛏️"

## Slack Posting

### Setup (one-time)

1. Create `#drawma` channel (or use existing)
2. Use existing Slack app or create new one
3. Add `chat:write` scope if not present
4. Invite bot to the channel

### Message Format

Just the prompt, nothing else:

```
📉 Local Fish Achieves Enlightenment Through Fiscal Policy, Refuses Comment 🐟
```

### Environment Variables (secrets)

```
SLACK_BOT_TOKEN=xoxb-...
GROQ_API_KEY=gsk_...
```

Stored in GitHub Actions secrets, not in repo.

## GitHub Actions

### Workflow: `.github/workflows/daily-prompt.yml`

```yaml
name: Daily Surreal Prompt

on:
  schedule:
    - cron: '0 15 * * *'  # 7am PT (3pm UTC)
  workflow_dispatch:       # Manual trigger button

jobs:
  post-prompt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r surreal-prompt-bot/requirements.txt
      - run: python surreal-prompt-bot/bot.py
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
```

### Features

- Runs at 7am PT daily
- Manual trigger button in GitHub UI for testing
- Secrets stored securely
- Free for public repos

## Project Structure

```
surreal-prompt-bot/
├── bot.py                 # Main script (CLI entrypoint)
├── config.yaml            # Default configuration
├── inspirations.txt       # Artistic inspiration lines
├── requirements.txt       # Dependencies
└── src/
    ├── __init__.py
    ├── scraper.py         # News scraping logic
    ├── generator.py       # Groq/LLM prompt generation
    └── slack_poster.py    # Slack posting
```

## Configuration

### Default config.yaml

```yaml
slack:
  channel: "#drawma"

prompt:
  temperature: 1.0
  model: llama-3.1-8b-instant
  max_headlines: 10

inspirations:
  file: inspirations.txt
  pick_count: 2

sources:
  - reuters
  - foxnews
  - cnn
  - bbc
  - ft
  - bloomberg
  - guardian
  - breitbart
```

### CLI Options

```bash
# Normal run
python bot.py

# Test without posting
python bot.py --dry-run

# Override settings
python bot.py --channel "#test" --temperature 1.5

# Specific sources only
python bot.py --sources reuters,bbc

# Skip inspiration file
python bot.py --no-inspirations
```

## Error Handling

- Source fails to scrape → Log warning, continue with others
- All sources fail → Exit with error, don't post
- Groq API fails → Exit with error, don't post
- Slack post fails → Exit with error, log the prompt

## Future Extensions

- Multiple prompts per day
- Image generation (DALL-E, Stable Diffusion)
- Voting on prompts
- Archive of past prompts

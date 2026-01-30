# Slack Song Title Generator

Generate chaotic geocities-style HTML pages from song titles in your Slack channel.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [Ollama](https://ollama.ai/) running locally with a model (llama3 recommended)
- A Slack workspace where you can create apps

## Installation

```bash
cd slack-song-generator
uv sync
```

## Slack App Setup (One-Time)

### 1. Create the App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name it something like "Song Title Fetcher"
4. Select your workspace
5. Click **Create App**

### 2. Add Permissions

1. In the left sidebar, click **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Click **Add an OAuth Scope** and add:
   - `channels:history` (read messages from public channels)
   - `channels:read` (list channels)

### 3. Install to Workspace

1. Scroll up and click **Install to Workspace**
2. Review permissions and click **Allow**
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 4. Invite Bot to Channel

1. In Slack, go to your song titles channel
2. Type `/invite @YourBotName` (use the name you gave your app)

### 5. Get Channel ID

1. Right-click on the channel name
2. Click **View channel details**
3. At the bottom, copy the **Channel ID** (starts with `C`)

### 6. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values:
# SLACK_BOT_TOKEN=xoxb-your-token-here
# SLACK_CHANNEL_ID=C0XXXXXXX
```

## Ollama Setup

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama
ollama serve

# Pull a model (in another terminal)
ollama pull llama3
```

## Usage

```bash
# Basic generation
./generate-song-page.py --output ../songtitles.html

# Pure chaos mode (randomize all settings)
./generate-song-page.py --random --output ../songtitles.html

# Reproducible chaos (same seed = same layout)
./generate-song-page.py --random --seed 42 --output ../songtitles.html

# With scattered images
./generate-song-page.py --media-dir ./gifs --output ../songtitles.html

# Just fetch and cache titles (no HTML generation)
./generate-song-page.py --fetch-only

# Regenerate from cache (skip Slack API call)
./generate-song-page.py --generate-only --random
```

## All Options

| Option | Description | Default |
|--------|-------------|---------|
| `--channel-id` | Slack channel ID (overrides .env) | from .env |
| `--output` | Output HTML file path | songtitles.html |
| `--seed` | Random seed for reproducible chaos | random |
| `--media-dir` | Directory of images/GIFs to scatter | none |
| `--density` | How packed/sparse (1-10) | 5 |
| `--color-palette` | neon, pastel, mono, or random | neon |
| `--font-chaos` | How many fonts to use (1-5) | 5 |
| `--max-rotation` | Max rotation degrees | 30 |
| `--title-limit` | Max titles to fetch | 500 |
| `--fetch-only` | Only fetch/filter, no HTML | false |
| `--generate-only` | Use cache, skip Slack | false |
| `--random` | Randomize all visual settings | false |

## Troubleshooting

**"Error connecting to Ollama"**
- Make sure Ollama is running: `ollama serve`
- Check if model is pulled: `ollama list`

**"SLACK_BOT_TOKEN not set"**
- Copy `.env.example` to `.env` and fill in your token

**"channel_not_found" error**
- Make sure the bot is invited to the channel
- Verify the channel ID is correct

**No titles found after filtering**
- The channel might have mostly discussion, not titles
- Try with `--fetch-only` to see raw messages in cache

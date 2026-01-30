# Surreal Prompt Bot

A daily Slack bot that generates surrealist drawing prompts inspired by news headlines.

## How It Works

1. Scrapes headlines from diverse news sources (FT, Fox News, CNN, Reuters, BBC, etc.)
2. Picks random artistic inspirations from `inspirations.txt`
3. Feeds both to Groq's free Llama API
4. Posts a surreal headline-style drawing prompt to Slack

## Setup

### 1. Get API Keys

- **Groq**: Free at https://console.groq.com
- **Slack**: Create app at https://api.slack.com/apps with `chat:write` scope

### 2. Configure GitHub Secrets

In your repo settings, add:
- `GROQ_API_KEY`
- `SLACK_BOT_TOKEN`

### 3. Invite Bot to Channel

Invite your Slack bot to `#drawma` (or your chosen channel).

## Local Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="gsk_..."
export SLACK_BOT_TOKEN="xoxb-..."

# Dry run (no Slack posting)
python bot.py --dry-run

# Post to default channel (#drawma)
python bot.py

# Post to different channel
python bot.py --channel "#test"

# Use specific sources only
python bot.py --sources reuters,bbc

# Skip inspirations
python bot.py --no-inspirations

# Adjust creativity
python bot.py --temperature 1.5
```

## Configuration

Edit `config.yaml` to change defaults:

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

## Adding Inspirations

Edit `inspirations.txt`, one per line:

```
corporate memphis art style
deep fried meme aesthetic
vaporwave capitalism
```

## Example Outputs

- "Local Fish Achieves Enlightenment Through Fiscal Policy, Refuses Comment"
- "The Moon Files For Bankruptcy While Clouds Hold Emergency Session"
- "Breaking: Your Childhood Bedroom Now A Subsidiary Of Feelings Inc."

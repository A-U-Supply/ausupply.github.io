# Muzzik Playlist Bot — Design

**Date:** 2026-02-11
**Status:** Implemented

## Overview

A bot that scrapes the #muzzik Slack channel for YouTube URLs and maintains an unlisted YouTube playlist with every video shared. Runs daily as a GitHub Action. Logs all URLs (YouTube and non-YouTube) to a state file committed to git.

## Architecture

### Components

```
muzzik-bot/
  bot.py              # Main orchestrator
  auth_setup.py       # One-time local OAuth helper (get refresh token)
  requirements.txt    # google-api-python-client, google-auth-oauthlib, slack-sdk
  state.json          # URL log + playlist state (committed to git)
.github/workflows/
  muzzik-playlist.yml # Daily cron
```

### Flow

1. Scrape all messages from #muzzik (cursor-based pagination, same pattern as `scrape_gallery.py`)
2. Extract all URLs from message text via regex
3. Classify each as `youtube` or `other`, deduplicate against `state.json`
4. Log all new URLs to `state.json`
5. Queue new YouTube video IDs into backlog (newest first for priority)
6. Authenticate with YouTube via refresh token
7. Process up to ~190 videos from backlog: insert at position 0 of current playlist
8. If current playlist hits 5,000 videos: create a new unlisted volume, continue
9. Save updated `state.json`

## YouTube API Setup

### One-time setup (manual)

1. Create a Google Cloud project
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (type: "Desktop app") — yields `client_id` and `client_secret`
4. Run `muzzik-bot/auth_setup.py` locally — opens browser, log in with the label's YouTube account, grant playlist permissions, prints a `refresh_token`
5. Store as GitHub secrets: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`

### Runtime authentication

- Bot uses the refresh token to obtain a short-lived access token (no browser needed)
- OAuth scope: `https://www.googleapis.com/auth/youtube`

### Quota

- YouTube Data API default quota: 10,000 units/day
- `playlistItems.insert`: 50 units each
- Safe daily cap: ~190 video inserts (leaves headroom for other API calls)
- Backlog drains over multiple days if the channel has a large history

## State File

`muzzik-bot/state.json` — committed to git after each run.

```json
{
  "playlists": [
    {"id": "PLxyz...", "title": "muzzik vol. 1", "count": 5000},
    {"id": "PLabc...", "title": "muzzik vol. 2", "count": 312}
  ],
  "urls": [
    {
      "url": "https://youtu.be/dQw4w9...",
      "video_id": "dQw4w9...",
      "type": "youtube",
      "added_to_playlist": true,
      "date": "2025-03-15",
      "user": "U12345"
    },
    {
      "url": "https://soundcloud.com/...",
      "video_id": null,
      "type": "other",
      "added_to_playlist": false,
      "date": "2025-03-14",
      "user": "U67890"
    }
  ],
  "backlog": ["dQw4w9..."]
}
```

- Every URL from #muzzik gets an entry in `urls`
- YouTube URLs get a `video_id` and flow through the playlist pipeline
- Non-YouTube URLs are logged with `type: "other"` and ignored for playlist purposes
- Deduplication checks against `urls` so the same link isn't logged twice

## Playlist Management

- **Unlisted**: All playlists created as unlisted
- **Ordering**: Reverse chronological — new videos inserted at position 0 (newest at top)
- **Rollover**: When a playlist hits 5,000 videos (YouTube's hard limit), the bot creates a new unlisted playlist ("muzzik vol. 2", "muzzik vol. 3", etc.) and continues adding there
- **No deletion**: Old playlists and videos are never removed

## Backlog Strategy

On first run (or if channel has a large history), there may be more YouTube URLs than can be added in one day (~190 cap).

- New URLs from the current scrape are added to the backlog
- Newer videos get priority — inserted before older backlog items
- Each run processes up to ~190 from the backlog
- Backlog persists in `state.json` across runs
- Example: 800 URLs in history = ~4-5 days to fully backfill

## GitHub Action

**Workflow: `muzzik-playlist.yml`**

| Field | Value |
|-------|-------|
| Trigger | Cron `0 8 * * *` (8am UTC) + manual `workflow_dispatch` |
| Permissions | `contents: write` |
| Python | 3.11 |
| Secrets | `SLACK_BOT_TOKEN` (existing), `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` |

Steps:
1. Checkout repo
2. Install Python dependencies from `muzzik-bot/requirements.txt`
3. Run `python muzzik-bot/bot.py`
4. Commit `muzzik-bot/state.json` if changed (same pattern as `scrape-drawma.yml`)

Git commit author: `github-actions[bot]`

## Slack Requirements

- Reuses existing `SLACK_BOT_TOKEN`
- Required scopes (already granted): `channels:history`, `channels:read`
- No new Slack scopes needed

## YouTube URL Extraction

Regex matches these formats:
- `youtube.com/watch?v=VIDEO_ID`
- `youtu.be/VIDEO_ID`
- `youtube.com/shorts/VIDEO_ID`
- `youtube.com/live/VIDEO_ID`
- Handles additional query params and timestamps

## Dependencies

`requirements.txt`:
```
google-api-python-client
google-auth-oauthlib
slack-sdk
```

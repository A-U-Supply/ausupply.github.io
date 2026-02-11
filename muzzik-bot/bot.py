#!/usr/bin/env python3
"""Muzzik playlist bot - scrapes #muzzik Slack channel and updates a YouTube playlist."""

import argparse
import logging
import os
import sys
from pathlib import Path

from slack_sdk import WebClient

from slack_scraper import find_channel_id, fetch_all_messages, extract_urls_from_messages
from state import load_state, save_state, add_urls_to_state, get_new_urls
from youtube import get_youtube_client, process_backlog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CHANNEL_NAME = "#muzzik"
STATE_PATH = Path(__file__).parent / "state.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Muzzik playlist bot")
    parser.add_argument("--dry-run", action="store_true", help="Skip YouTube API calls")
    args = parser.parse_args()

    # --- Slack scraping ---
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    client = WebClient(token=slack_token)
    channel_id = find_channel_id(client, CHANNEL_NAME)
    if not channel_id:
        logger.error(f"Channel {CHANNEL_NAME} not found")
        return 1
    logger.info(f"Found channel {CHANNEL_NAME}: {channel_id}")

    messages = fetch_all_messages(client, channel_id)
    url_entries = extract_urls_from_messages(messages)
    logger.info(f"Extracted {len(url_entries)} unique URLs ({sum(1 for u in url_entries if u['type'] == 'youtube')} YouTube)")

    # --- State management ---
    state = load_state(STATE_PATH)
    new_urls = get_new_urls(url_entries, state["urls"])
    logger.info(f"Found {len(new_urls)} new URLs")

    if not new_urls and not state["backlog"]:
        logger.info("Nothing new and backlog is empty — done")
        save_state(state, STATE_PATH)
        return 0

    add_urls_to_state(state, new_urls)

    # --- YouTube playlist ---
    if args.dry_run:
        logger.info(f"[DRY RUN] Backlog has {len(state['backlog'])} videos")
        save_state(state, STATE_PATH)
        return 0

    yt_client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    yt_client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    yt_refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not all([yt_client_id, yt_client_secret, yt_refresh_token]):
        logger.error("YouTube credentials not set (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN)")
        return 1

    youtube = get_youtube_client(yt_client_id, yt_client_secret, yt_refresh_token)
    added = process_backlog(youtube, state)
    logger.info(f"Playlist update complete: {added} videos added")

    save_state(state, STATE_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())

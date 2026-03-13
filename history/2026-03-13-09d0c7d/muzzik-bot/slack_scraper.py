# muzzik-bot/slack_scraper.py
"""Slack channel scraper for extracting URLs from #muzzik."""

import logging

from slack_sdk import WebClient

from urls import extract_urls, extract_video_id, classify_url

logger = logging.getLogger(__name__)


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Find a channel ID by name. Returns None if not found."""
    name = channel_name.lstrip("#")
    cursor = None
    while True:
        kwargs = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


def fetch_all_messages(client: WebClient, channel_id: str) -> list[dict]:
    """Fetch ALL channel messages (no time limit)."""
    messages = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)
        messages.extend(resp["messages"])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    logger.info(f"Fetched {len(messages)} messages")
    return messages


def _ts_to_date(ts: str) -> str:
    """Convert a Slack timestamp to a UTC date string."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def extract_urls_from_messages(messages: list[dict]) -> list[dict]:
    """Extract and classify all URLs from a list of Slack messages.

    Returns a list of dicts: {url, video_id, type, date, user}
    """
    results = []
    seen_urls = set()
    for msg in messages:
        text = msg.get("text", "")
        if not text:
            continue
        urls = extract_urls(text)
        date = _ts_to_date(msg["ts"])
        user = msg.get("user", "unknown")
        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            url_type = classify_url(url)
            video_id = extract_video_id(url) if url_type == "youtube" else None
            results.append({
                "url": url,
                "video_id": video_id,
                "type": url_type,
                "date": date,
                "user": user,
            })
    return results

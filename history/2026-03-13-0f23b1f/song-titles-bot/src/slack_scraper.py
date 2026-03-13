"""Fetch song title messages from Slack #song-titles channel."""
import logging
from datetime import datetime, timezone

from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Find a Slack channel ID by name."""
    cursor = None
    while True:
        kwargs = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == channel_name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


def fetch_new_messages(
    client: WebClient,
    channel_name: str,
    after_ts: str | None = None,
) -> list[dict]:
    """Fetch human messages from #song-titles, optionally only those newer than after_ts.

    Returns list of dicts with keys: id, title, date, author_id, permalink.
    Messages are returned newest-first.
    """
    channel_id = find_channel_id(client, channel_name)
    if not channel_id:
        logger.error(f"Channel #{channel_name} not found")
        return []

    messages = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        if after_ts:
            kwargs["oldest"] = after_ts

        resp = client.conversations_history(**kwargs)

        for msg in resp.get("messages", []):
            if "bot_id" in msg or "subtype" in msg:
                continue
            if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]:
                continue

            text = msg.get("text", "").strip()
            if not text:
                continue

            if after_ts and float(msg["ts"]) <= float(after_ts):
                continue

            ts = msg["ts"]
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)

            messages.append({
                "id": ts,
                "title": text,
                "date": dt.strftime("%Y-%m-%d"),
                "author_id": msg.get("user"),
                "permalink": f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
            })

        if resp.get("has_more"):
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        else:
            break

    logger.info(f"Fetched {len(messages)} new messages from #{channel_name}")
    return messages

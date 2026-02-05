#!/usr/bin/env python3
"""Drawma gallery scraper - downloads drawings from the #drawma Slack channel."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from slack_sdk import WebClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CHANNEL_NAME = "#drawma"
REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / "img" / "drawma"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
PROMPTS_PATH = OUTPUT_DIR / "prompts.json"


def _ts_to_date(ts: str) -> str:
    """Convert a Slack timestamp to a UTC date string (YYYY-MM-DD)."""
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def get_bot_user_id(client: WebClient) -> str:
    """Get the bot's own user ID via auth_test."""
    resp = client.auth_test()
    return resp["user_id"]


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


def fetch_channel_messages(client: WebClient, channel_id: str, days_back: int = 7) -> list[dict]:
    """Fetch recent channel messages via conversations_history."""
    oldest = datetime.now(tz=timezone.utc).timestamp() - (days_back * 86400)
    messages = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "oldest": str(oldest), "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)
        messages.extend(resp["messages"])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages


def fetch_thread_replies(client: WebClient, channel_id: str, thread_ts: str) -> list[dict]:
    """Fetch thread replies, excluding the parent message."""
    replies = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_replies(**kwargs)
        replies.extend(resp["messages"])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    # First message in replies is the parent; skip it
    return replies[1:] if replies else []


def extract_images_from_messages(messages: list[dict]) -> list[dict]:
    """Extract image files from Slack messages.

    Returns a list of dicts with file info, message_ts, and user.
    Only includes files whose mimetype starts with 'image/'.
    """
    images = []
    for msg in messages:
        files = msg.get("files", [])
        for f in files:
            if not f.get("mimetype", "").startswith("image/"):
                continue
            images.append({
                "file_id": f["id"],
                "name": f["name"],
                "mimetype": f["mimetype"],
                "url": f["url_private_download"],
                "width": f.get("original_w"),
                "height": f.get("original_h"),
                "message_ts": msg["ts"],
                "user": msg.get("user"),
            })
    return images


def associate_images_with_prompts(images: list[dict], prompts: list[dict]) -> list[dict]:
    """Match images to bot prompts from the same UTC day.

    Each image dict gets a 'prompt' key added (text or None).
    Returns a new list (does not mutate the originals).
    """
    # Build date -> prompt text mapping
    prompt_by_date: dict[str, str] = {}
    for p in prompts:
        date = _ts_to_date(p["ts"])
        prompt_by_date[date] = p["text"]

    result = []
    for img in images:
        entry = dict(img)
        date = _ts_to_date(img["message_ts"])
        entry["prompt"] = prompt_by_date.get(date)
        result.append(entry)
    return result


def filter_new_images(images: list[dict], manifest: list[dict]) -> list[dict]:
    """Filter out images whose file ID is already in the manifest."""
    existing_ids = {entry["id"] for entry in manifest}
    return [img for img in images if img["file_id"] not in existing_ids]


def _download_with_auth(url: str, token: str, timeout: int = 30) -> requests.Response:
    """Download a URL, manually following redirects to preserve the auth header.

    The requests library strips Authorization headers on cross-domain redirects
    (a security feature). Slack's url_private_download redirects to a CDN on a
    different host, so we must follow redirects ourselves.
    """
    headers = {"Authorization": f"Bearer {token}"}
    max_redirects = 5
    for _ in range(max_redirects):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp
    raise requests.TooManyRedirects(f"Too many redirects for {url}")


def download_image(image: dict, output_dir: Path, token: str) -> dict:
    """Download an image and return a manifest entry dict.

    Saves as {date}-{file_id}.{ext} in output_dir.
    """
    date = _ts_to_date(image["message_ts"])
    ext = Path(image["name"]).suffix.lstrip(".")
    filename = f"{date}-{image['file_id']}.{ext}"
    filepath = output_dir / filename

    resp = _download_with_auth(image["url"], token)

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise ValueError(
            f"Expected image content, got '{content_type}' for {image['file_id']}"
        )

    filepath.write_bytes(resp.content)

    logger.info(f"Downloaded {filename} ({len(resp.content)} bytes)")

    return {
        "id": image["file_id"],
        "filename": filename,
        "date": date,
        "prompt": image.get("prompt"),
        "artist": image.get("artist"),
        "width": image.get("width"),
        "height": image.get("height"),
    }


def get_slack_username(client: WebClient, user_id: str) -> str:
    """Look up a Slack user's display name."""
    try:
        resp = client.users_info(user=user_id)
        profile = resp["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        logger.warning(f"Could not resolve username for {user_id}")
        return user_id


def load_manifest() -> list[dict]:
    """Load existing manifest from disk."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return []


def save_manifest(manifest: list[dict]) -> None:
    """Save manifest to disk, sorted by date descending."""
    manifest.sort(key=lambda e: e.get("date", ""), reverse=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info(f"Saved manifest with {len(manifest)} entries")


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
    return messages


def save_prompts(prompt_texts: list[str]) -> None:
    """Save all bot prompt texts to prompts.json for the gallery whispers."""
    PROMPTS_PATH.write_text(json.dumps(prompt_texts, indent=2) + "\n")
    logger.info(f"Saved {len(prompt_texts)} prompts to prompts.json")


def main() -> int:
    """Orchestrate the full scrape: fetch messages, find images, download new ones."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    client = WebClient(token=token)

    # Get bot user ID so we can identify bot prompts
    bot_user_id = get_bot_user_id(client)
    logger.info(f"Bot user ID: {bot_user_id}")

    # Find the channel
    channel_id = find_channel_id(client, CHANNEL_NAME)
    if not channel_id:
        logger.error(f"Channel {CHANNEL_NAME} not found")
        return 1
    logger.info(f"Found channel {CHANNEL_NAME}: {channel_id}")

    # Fetch ALL messages for prompts (full history)
    all_messages = fetch_all_messages(client, channel_id)
    logger.info(f"Fetched {len(all_messages)} total messages from channel history")

    # Identify bot prompts (messages from the bot) — full history
    all_prompts = [
        {"text": m["text"], "ts": m["ts"]}
        for m in all_messages
        if m.get("user") == bot_user_id or m.get("bot_id")
    ]
    logger.info(f"Found {len(all_prompts)} bot prompts (all time)")

    # Save all prompt texts for gallery whispers
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_texts = [
        p["text"] for p in all_prompts
        if p["text"].strip() and "has joined the channel" not in p["text"]
    ]
    save_prompts(prompt_texts)

    # Use recent messages for image discovery
    messages = fetch_channel_messages(client, channel_id)

    # Collect images from top-level messages
    all_images = extract_images_from_messages(messages)

    # Also collect images from threads (replies to bot prompts)
    for m in messages:
        if m.get("reply_count", 0) > 0:
            replies = fetch_thread_replies(client, channel_id, m["ts"])
            all_images.extend(extract_images_from_messages(replies))

    logger.info(f"Found {len(all_images)} total images")

    # Associate images with prompts
    all_images = associate_images_with_prompts(all_images, all_prompts)

    # Filter out already-downloaded images
    manifest = load_manifest()
    new_images = filter_new_images(all_images, manifest)
    logger.info(f"Found {len(new_images)} new images to download")

    if not new_images:
        logger.info("No new images to download")
        return 0

    # Resolve usernames
    username_cache: dict[str, str] = {}
    for img in new_images:
        uid = img.get("user")
        if uid and uid not in username_cache:
            username_cache[uid] = get_slack_username(client, uid)
        img["artist"] = username_cache.get(uid, uid)

    # Download images and build manifest entries
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    new_entries = []
    for img in new_images:
        try:
            entry = download_image(img, OUTPUT_DIR, token)
            new_entries.append(entry)
        except Exception as e:
            logger.error(f"Failed to download {img['file_id']}: {e}")

    # Save updated manifest
    manifest.extend(new_entries)
    save_manifest(manifest)

    logger.info(f"Downloaded {len(new_entries)} new images")
    return 0


if __name__ == "__main__":
    sys.exit(main())

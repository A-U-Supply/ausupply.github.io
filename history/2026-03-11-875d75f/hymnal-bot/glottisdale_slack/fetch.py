"""Fetch video files from a Slack channel."""

import logging
import random
from pathlib import Path

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Resolve channel name to ID via cursor pagination."""
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
            return None


def find_video_messages(client: WebClient, channel_id: str) -> list[dict]:
    """Find all messages with video attachments in a channel."""
    videos = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)
        for msg in resp.get("messages", []):
            for f in msg.get("files", []):
                if f.get("mimetype", "").startswith("video/"):
                    videos.append({
                        "file": f,
                        "ts": msg["ts"],
                        "text": msg.get("text", ""),
                    })
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return videos


def _download_with_auth(url: str, token: str, timeout: int = 60) -> requests.Response:
    """Download a file, manually following redirects to preserve auth."""
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


def fetch_videos(
    token: str,
    channel: str,
    max_videos: int,
    download_dir: Path,
) -> list[dict]:
    """Fetch random video files from a Slack channel.

    Returns:
        List of dicts with 'path' (Path to downloaded file) and 'permalink' keys.
    """
    client = WebClient(token=token)

    channel_id = find_channel_id(client, channel)
    if not channel_id:
        raise ValueError(f"Channel not found: {channel}")

    video_msgs = find_video_messages(client, channel_id)
    if not video_msgs:
        return []

    # Random sample
    selected = random.sample(video_msgs, min(max_videos, len(video_msgs)))

    results = []
    for msg in selected:
        f = msg["file"]
        url = f["url_private_download"]
        name = f.get("name", f"video_{f['id']}.mp4")
        dest = download_dir / name

        logger.info(f"Downloading {name}...")
        resp = _download_with_auth(url, token)

        # Validate content type
        content_type = resp.headers.get("Content-Type", "")
        if "video" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"Unexpected content type for {name}: {content_type}, skipping")
            continue

        dest.write_bytes(resp.content)

        permalink = f"https://slack.com/archives/{channel_id}/p{msg['ts'].replace('.', '')}"
        results.append({
            "path": dest,
            "permalink": permalink,
            "name": name,
            "file_id": f["id"],
        })

    return results

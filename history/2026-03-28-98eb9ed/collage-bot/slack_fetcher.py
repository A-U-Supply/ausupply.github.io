"""Fetch random images from a Slack channel."""
import logging
import random
from pathlib import Path

from typing import Optional

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

IMAGE_MIME_PREFIXES = ("image/jpeg", "image/png", "image/gif", "image/webp")


def find_channel_id(client: WebClient, channel_name: str) -> Optional[str]:
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


def _download_with_auth(url: str, token: str, timeout: int = 30) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp.content
    raise requests.TooManyRedirects(f"Too many redirects for {url}")


def fetch_random_images(
    token: str,
    channel: str,
    count: int,
    download_dir: Path,
) -> list[Path]:
    """Fetch `count` random images from channel, download to download_dir."""
    client = WebClient(token=token)
    channel_name = channel.lstrip("#")
    channel_id = find_channel_id(client, channel_name)
    if not channel_id:
        raise ValueError(f"Channel #{channel_name} not found")

    # Collect all image file metadata from channel history
    all_images = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)

        for msg in resp["messages"]:
            for f in msg.get("files", []):
                mimetype = f.get("mimetype", "")
                if any(mimetype.startswith(p) for p in IMAGE_MIME_PREFIXES):
                    url = f.get("url_private_download") or f.get("url_private")
                    if url:
                        ext = f.get("filetype", "jpg")
                        all_images.append({"url": url, "ext": ext, "id": f["id"]})

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    if len(all_images) < count:
        raise ValueError(f"Only {len(all_images)} images found in #{channel_name}, need {count}")

    selected = random.sample(all_images, count)
    download_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, img in enumerate(selected):
        dest = download_dir / f"source_{i}.{img['ext']}"
        data = _download_with_auth(img["url"], token)
        dest.write_bytes(data)
        logger.info(f"Downloaded {dest.name}")
        paths.append(dest)

    return paths

"""URL extraction and classification utilities."""

import re
from urllib.parse import urlparse, parse_qs


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from Slack message text.

    Handles Slack's angle-bracket format: <url> and <url|label>
    """
    urls = []
    # Slack-formatted URLs: <url> or <url|label>
    for match in re.finditer(r"<(https?://[^>|]+)(?:\|[^>]*)?>", text):
        urls.append(match.group(1))
    # Plain URLs not in angle brackets
    # Negative lookbehind for < to avoid double-matching Slack URLs
    for match in re.finditer(r"(?<![\<|])https?://[^\s<>\"')\]]+", text):
        url = match.group(0)
        if url not in urls:
            urls.append(url)
    return urls


def extract_video_id(url: str) -> str | None:
    """Extract a YouTube video ID from a URL. Returns None if not a video URL."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    # Strip www. prefix
    if host.startswith("www."):
        host = host[4:]

    # youtu.be/VIDEO_ID
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
        return video_id if video_id else None

    # youtube.com or music.youtube.com
    if host not in ("youtube.com", "music.youtube.com"):
        return None

    path = parsed.path

    # /watch?v=VIDEO_ID
    if path == "/watch":
        v = parse_qs(parsed.query).get("v")
        return v[0] if v else None

    # /shorts/VIDEO_ID, /live/VIDEO_ID, /embed/VIDEO_ID
    for prefix in ("/shorts/", "/live/", "/embed/"):
        if path.startswith(prefix):
            video_id = path[len(prefix):].split("/")[0].split("?")[0]
            return video_id if video_id else None

    return None


def classify_url(url: str) -> str:
    """Classify a URL as 'youtube' or 'other'."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    if host in ("youtube.com", "youtu.be", "music.youtube.com"):
        return "youtube"
    return "other"

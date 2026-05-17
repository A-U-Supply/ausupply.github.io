#!/usr/bin/env python3
"""One-off: build a YouTube playlist from a specific Slack thread."""

import logging
import os
import re
import sys
from urllib.parse import urlparse, parse_qs

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from slack_sdk import WebClient

CHANNEL_ID = "C03TFJUE36G"
THREAD_TS = "1775047742.993089"
PLAYLIST_TITLE = "Regular Expression Inspo"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for m in re.finditer(r"<(https?://[^>|]+)(?:\|[^>]*)?>", text):
        urls.append(m.group(1))
    for m in re.finditer(r"(?<![\<|])https?://[^\s<>\"')\]]+", text):
        if m.group(0) not in urls:
            urls.append(m.group(0))
    return urls


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").removeprefix("www.")
    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None
    if host not in ("youtube.com", "music.youtube.com"):
        return None
    if parsed.path == "/watch":
        v = parse_qs(parsed.query).get("v")
        return v[0] if v else None
    for prefix in ("/shorts/", "/live/", "/embed/"):
        if parsed.path.startswith(prefix):
            vid = parsed.path[len(prefix):].split("/")[0].split("?")[0]
            return vid or None
    return None


def fetch_thread_video_ids(client: WebClient) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    cursor = None
    while True:
        kwargs = {"channel": CHANNEL_ID, "ts": THREAD_TS, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_replies(**kwargs)
        for msg in resp["messages"]:
            for url in extract_urls(msg.get("text", "")):
                vid = extract_video_id(url)
                if vid and vid not in seen:
                    seen.add(vid)
                    ordered.append(vid)
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return ordered


def main() -> int:
    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    video_ids = fetch_thread_video_ids(slack)
    log.info(f"Found {len(video_ids)} unique YouTube video IDs in thread")
    log.info("--- VIDEO IDS (in thread order) ---")
    for i, vid in enumerate(video_ids, start=1):
        log.info(f"  {i:>3}. https://youtu.be/{vid}")
    log.info("--- end IDS ---")
    if not video_ids:
        log.info("Nothing to add. Exiting.")
        return 0

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    pl = yt.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": PLAYLIST_TITLE},
            "status": {"privacyStatus": "unlisted"},
        },
    ).execute()
    playlist_id = pl["id"]
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    log.info(f"Created playlist: {playlist_url}")

    failures: list[tuple[str, str]] = []
    for i, vid in enumerate(video_ids, start=1):
        try:
            yt.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": vid},
                    }
                },
            ).execute()
            log.info(f"  [{i}/{len(video_ids)}] added {vid}")
        except HttpError as e:
            log.warning(f"  [{i}/{len(video_ids)}] FAILED {vid}: {e}")
            failures.append((vid, str(e)))

    log.info("")
    log.info(f"PLAYLIST URL: {playlist_url}")
    log.info(f"Added: {len(video_ids) - len(failures)} / {len(video_ids)}")
    if failures:
        log.info(f"Failures: {len(failures)}")
        for vid, err in failures:
            log.info(f"  - {vid}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

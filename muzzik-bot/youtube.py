# muzzik-bot/youtube.py
"""YouTube Data API v3 playlist management."""

import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube"]
MAX_PLAYLIST_SIZE = 5000
DAILY_INSERT_CAP = 190  # ~10,000 quota / 50 units per insert, with headroom


def get_youtube_client(client_id: str, client_secret: str, refresh_token: str):
    """Build an authenticated YouTube API client using a refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)


def create_playlist(youtube, title: str) -> str:
    """Create an unlisted YouTube playlist. Returns the playlist ID."""
    resp = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": "Music shared in #muzzik"},
            "status": {"privacyStatus": "unlisted"},
        },
    ).execute()
    playlist_id = resp["id"]
    logger.info(f"Created playlist '{title}': {playlist_id}")
    return playlist_id


def add_video_to_playlist(youtube, playlist_id: str, video_id: str) -> bool:
    """Add a video to a playlist at position 0 (top). Returns True on success."""
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "position": 0,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                },
            },
        ).execute()
        logger.info(f"Added {video_id} to playlist {playlist_id}")
        return True
    except HttpError as e:
        if e.resp.status == 403 and "quota" in str(e).lower():
            raise  # Quota exceeded — stop the run
        if e.resp.status in (400, 403, 404):
            logger.warning(f"Video {video_id} skipped (HTTP {e.resp.status}: {e.reason})")
            return False
        raise


def get_or_create_playlist(youtube, state: dict) -> tuple[str, dict]:
    """Get the current playlist, or create one if needed.

    Returns (playlist_id, playlist_entry). Creates a new volume if the current
    playlist is full (5000 videos).
    """
    if state["playlists"]:
        current = state["playlists"][-1]
        if current["count"] < MAX_PLAYLIST_SIZE:
            return current["id"], current
        # Current playlist is full, create new volume
        vol = len(state["playlists"]) + 1
    else:
        vol = 1

    title = f"muzzik vol. {vol}"
    playlist_id = create_playlist(youtube, title)
    entry = {"id": playlist_id, "title": title, "count": 0}
    state["playlists"].append(entry)
    return playlist_id, entry


def get_playlist_video_ids(youtube, playlist_id: str) -> set[str]:
    """Fetch all video IDs currently in a playlist."""
    video_ids = set()
    request = youtube.playlistItems().list(
        part="contentDetails", playlistId=playlist_id, maxResults=50
    )
    while request:
        resp = request.execute()
        for item in resp.get("items", []):
            video_ids.add(item["contentDetails"]["videoId"])
        request = youtube.playlistItems().list_next(request, resp)
    return video_ids


def process_backlog(youtube, state: dict, dry_run: bool = False) -> int:
    """Process the video backlog, adding up to DAILY_INSERT_CAP videos.

    Returns the number of videos successfully added.
    """
    if not state["backlog"]:
        logger.info("Backlog is empty, nothing to add")
        return 0

    if dry_run:
        count = min(len(state["backlog"]), DAILY_INSERT_CAP)
        logger.info(f"[DRY RUN] Would add {count} videos from backlog of {len(state['backlog'])}")
        return 0

    playlist_id, playlist_entry = get_or_create_playlist(youtube, state)
    added = 0
    remaining = []

    # Fetch existing playlist contents to avoid duplicates
    existing_ids = get_playlist_video_ids(youtube, playlist_id)
    if existing_ids:
        logger.info(f"Playlist already has {len(existing_ids)} videos, will skip duplicates")

    # Build lookup for marking urls as added
    video_id_to_url = {}
    for u in state["urls"]:
        if u.get("video_id") and not u["added_to_playlist"]:
            video_id_to_url.setdefault(u["video_id"], u)

    skipped_dupes = 0
    for video_id in state["backlog"]:
        if added >= DAILY_INSERT_CAP:
            remaining.append(video_id)
            continue

        # Skip videos already in the playlist
        if video_id in existing_ids:
            skipped_dupes += 1
            if video_id in video_id_to_url:
                video_id_to_url[video_id]["added_to_playlist"] = True
            continue

        # Check if we need a new playlist
        if playlist_entry["count"] >= MAX_PLAYLIST_SIZE:
            playlist_id, playlist_entry = get_or_create_playlist(youtube, state)
            existing_ids = get_playlist_video_ids(youtube, playlist_id)

        success = add_video_to_playlist(youtube, playlist_id, video_id)
        if success:
            playlist_entry["count"] += 1
            added += 1
            existing_ids.add(video_id)
        # Mark as added in urls list (even if video was unavailable — don't retry)
        if video_id in video_id_to_url:
            video_id_to_url[video_id]["added_to_playlist"] = True

    state["backlog"] = remaining
    logger.info(f"Added {added} videos, skipped {skipped_dupes} duplicates, {len(remaining)} remaining in backlog")
    return added

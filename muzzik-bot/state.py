"""State file management for the muzzik playlist bot."""

import json
from pathlib import Path

DEFAULT_STATE = {
    "playlists": [],
    "urls": [],
    "backlog": [],
}


def load_state(path: Path) -> dict:
    """Load state from disk. Returns default state if file doesn't exist."""
    if path.exists():
        return json.loads(path.read_text())
    return dict(DEFAULT_STATE)


def save_state(state: dict, path: Path) -> None:
    """Save state to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def get_new_urls(candidates: list[dict], existing: list[dict]) -> list[dict]:
    """Return only URLs not already in the existing list."""
    known = {e["url"] for e in existing}
    return [c for c in candidates if c["url"] not in known]


def add_urls_to_state(state: dict, new_urls: list[dict]) -> None:
    """Add new URLs to state. YouTube URLs also get added to backlog.

    New YouTube videos are prepended to backlog (newest get priority).
    Mutates state in place.
    """
    known = {e["url"] for e in state["urls"]}
    new_video_ids = []
    for entry in new_urls:
        if entry["url"] in known:
            continue
        state["urls"].append({
            "url": entry["url"],
            "video_id": entry.get("video_id"),
            "type": entry["type"],
            "added_to_playlist": False,
            "date": entry.get("date"),
            "user": entry.get("user"),
        })
        known.add(entry["url"])
        if entry["type"] == "youtube" and entry.get("video_id"):
            new_video_ids.append(entry["video_id"])
    # Prepend new videos to backlog (newest first)
    state["backlog"] = new_video_ids + state["backlog"]

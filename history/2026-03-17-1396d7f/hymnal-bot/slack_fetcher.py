"""Fetch MIDI files from #midieval and videos from #sample-sale."""
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

MIDIEVAL_CHANNEL = "midieval"
SAMPLE_SALE_CHANNEL = "sample-sale"
MIDI_FILENAMES = {"melody.mid", "drums.mid", "bass.mid", "chords.mid"}


def parse_midi_message(text: str) -> dict | None:
    """Parse a Daily MIDI bot message into metadata."""
    header = re.search(
        r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)', text
    )
    if not header:
        return None

    scale = header.group(1).strip()
    root = header.group(2)
    tempo = int(header.group(3))

    # Search for description only AFTER the *Daily MIDI* header
    text_after_header = text[header.end():]
    desc_match = re.search(r'_(.+?)_', text_after_header)
    description = desc_match.group(1) if desc_match else ""

    chords_match = re.search(r'Chords\s*—\s*(.+?)(?:\n|$)', text)
    chords = chords_match.group(1).split() if chords_match else []

    inst_match = re.search(r'MIDI\s+(\d+)', text)
    melody_instrument = int(inst_match.group(1)) if inst_match else 0

    temp_match = re.search(r'temperature\s+([\d.]+)', text)
    temperature = float(temp_match.group(1)) if temp_match else 1.0

    # Extract song title from first line (if present)
    title_match = re.match(r'^\*"(.+?)"\*', text)
    song_title = title_match.group(1) if title_match else None

    result = {
        "scale": scale,
        "root": root,
        "tempo": tempo,
        "description": description,
        "chords": chords,
        "melody_instrument": melody_instrument,
        "temperature": temperature,
    }
    if song_title:
        result["song_title"] = song_title

    return result


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


def _download_with_auth(url: str, token: str, timeout: int = 30) -> bytes:
    """Download preserving auth header across redirects."""
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp.content
    raise requests.TooManyRedirects(f"Too many redirects for {url}")


def fetch_latest_midi(
    token: str,
    download_dir: Path,
) -> tuple[dict | None, str | None]:
    """Fetch the most recent Daily MIDI post and its 4 MIDI files."""
    client = WebClient(token=token)
    channel_id = find_channel_id(client, MIDIEVAL_CHANNEL)
    if not channel_id:
        logger.error(f"Channel #{MIDIEVAL_CHANNEL} not found")
        return None, None

    cursor = None
    metadata = None
    thread_ts = None

    while True:
        kwargs = {"channel": channel_id, "limit": 50}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)

        for msg in resp["messages"]:
            parsed = parse_midi_message(msg.get("text", ""))
            if parsed:
                thread_ts = msg["ts"]
                ts_dt = datetime.fromtimestamp(float(thread_ts), tz=timezone.utc)
                parsed["date"] = ts_dt.strftime("%Y-%m-%d")
                metadata = parsed
                break

        if metadata:
            break

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    if not metadata or not thread_ts:
        logger.error("No Daily MIDI messages found")
        return None, None

    permalink = f"https://slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}"

    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_replies(**kwargs)

        for msg in resp["messages"]:
            for f in msg.get("files", []):
                name = f.get("name", "")
                if name not in MIDI_FILENAMES:
                    continue
                url = f.get("url_private_download") or f.get("url_private")
                if not url:
                    continue
                try:
                    data = _download_with_auth(url, token)
                    if not data.startswith(b"MThd"):
                        logger.warning(f"Invalid MIDI: {name}")
                        continue
                    (download_dir / name).write_bytes(data)
                    downloaded.append(name)
                except Exception as e:
                    logger.error(f"Failed to download {name}: {e}")

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    logger.info(f"Downloaded {len(downloaded)} MIDI files: {downloaded}")
    return metadata, permalink


def fetch_videos(
    token: str,
    download_dir: Path,
    max_videos: int = 5,
    channel: str = SAMPLE_SALE_CHANNEL,
) -> list[dict]:
    """Fetch random videos from #sample-sale using glottisdale_slack."""
    from glottisdale_slack.fetch import fetch_videos as _fetch

    return _fetch(
        token=token,
        channel=f"#{channel}",
        max_videos=max_videos,
        download_dir=download_dir,
    )

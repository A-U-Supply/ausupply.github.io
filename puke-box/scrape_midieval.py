"""Scrape #midieval Slack channel and archive MIDI bot output."""
import importlib.util
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

PUKE_BOX_DIR = Path(__file__).parent
MANIFEST_PATH = PUKE_BOX_DIR / "manifest.json"

CHANNEL_NAME = "midieval"
MIDI_FILENAMES = {"melody.mid", "drums.mid", "bass.mid", "chords.mid"}


def parse_midi_message(text: str) -> dict | None:
    """Parse a Daily MIDI message into structured metadata. Returns None if not a match."""
    header = re.search(
        r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)', text
    )
    if not header:
        return None

    scale, root, tempo = header.group(1), header.group(2), int(header.group(3))

    desc_match = re.search(r'_(.+?)_', text)
    description = desc_match.group(1) if desc_match else ""

    chords_match = re.search(r':musical_score: Chords\s*—\s*(.+)', text)
    chords = chords_match.group(1).split() if chords_match else []

    melody_match = re.search(r'Melody.*?MIDI\s+(\d+)', text)
    melody_instrument = int(melody_match.group(1)) if melody_match else 0

    temp_match = re.search(r'temperature\s+([\d.]+)', text)
    temperature = float(temp_match.group(1)) if temp_match else 1.0

    chord_instrument = 0

    return {
        "scale": scale,
        "root": root,
        "tempo": tempo,
        "description": description,
        "chords": chords,
        "melody_instrument": melody_instrument,
        "chord_instrument": chord_instrument,
        "temperature": temperature,
    }


def _download_with_auth(url: str, token: str, timeout: int = 30) -> bytes:
    """Download a URL, manually following redirects to preserve the auth header.

    The requests library strips Authorization headers on cross-domain redirects
    (a security feature). Slack's url_private_download redirects to a CDN on a
    different host, so we must follow redirects ourselves.

    Returns the response body as bytes.
    """
    headers = {"Authorization": f"Bearer {token}"}
    max_redirects = 5
    for _ in range(max_redirects):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp.content
    raise requests.TooManyRedirects(f"Too many redirects for {url}")


def find_channel_id(client: WebClient) -> str:
    """Find the #midieval channel ID by paginating through conversations_list.

    Raises ValueError if the channel is not found.
    """
    cursor = None
    while True:
        kwargs = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == CHANNEL_NAME:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"Channel #{CHANNEL_NAME} not found")


def fetch_midi_messages(client: WebClient, channel_id: str) -> list[dict]:
    """Fetch all Daily MIDI messages from channel history.

    Uses cursor-based pagination to walk the full history. Each message is
    parsed with parse_midi_message(); non-matching messages are skipped.
    Adds "date" (UTC YYYY-MM-DD from timestamp) and "thread_ts" fields.

    Returns a list of parsed metadata dicts.
    """
    results = []
    cursor = None
    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)
        for msg in resp["messages"]:
            parsed = parse_midi_message(msg.get("text", ""))
            if parsed is None:
                continue
            ts = msg["ts"]
            parsed["date"] = datetime.fromtimestamp(
                float(ts), tz=timezone.utc
            ).strftime("%Y-%m-%d")
            parsed["thread_ts"] = ts
            results.append(parsed)
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    logger.info(f"Found {len(results)} Daily MIDI messages")
    return results


def download_thread_midi_files(
    client: WebClient,
    channel_id: str,
    thread_ts: str,
    output_dir: str | Path,
    token: str,
) -> list[str]:
    """Download MIDI files from a thread's replies.

    Looks for file attachments whose name is in MIDI_FILENAMES
    (melody.mid, drums.mid, bass.mid, chords.mid). Uses
    _download_with_auth to handle Slack's redirect-based downloads.

    Returns a list of downloaded filenames.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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
                    logger.warning(f"No download URL for {name} in thread {thread_ts}")
                    continue
                try:
                    data = _download_with_auth(url, token)
                    if not data.startswith(b'MThd'):
                        logger.warning(f"{name}: not a valid MIDI file, skipping")
                        continue
                    filepath = output_dir / name
                    filepath.write_bytes(data)
                    downloaded.append(name)
                    logger.info(f"Downloaded {name} ({len(data)} bytes)")
                except Exception as e:
                    logger.error(f"Failed to download {name}: {e}")
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return downloaded


def _import_synthesizer():
    """Import synthesize_preview from midi-bot/src/synthesizer.py via importlib."""
    synth_path = Path(__file__).parent.parent / "midi-bot" / "src" / "synthesizer.py"
    spec = importlib.util.spec_from_file_location("midi_synthesizer", synth_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.synthesize_preview


def synthesize_ogg(midi_dir: Path) -> bool:
    """Synthesize MIDI files to OGG via WAV intermediate.

    Uses the midi-bot synthesizer to generate a WAV preview, then
    converts to OGG with ffmpeg for smaller file size.

    Returns True on success, False on failure.
    """
    wav_path = midi_dir / "preview.wav"
    ogg_path = midi_dir / "preview.ogg"

    try:
        synth_fn = _import_synthesizer()
        if not synth_fn(midi_dir, wav_path):
            logger.error("Synthesizer returned failure")
            return False
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return False

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "64k", str(ogg_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"ffmpeg conversion failed: {e}")
        return False
    finally:
        if wav_path.exists():
            wav_path.unlink()

    logger.info(f"OGG preview written: {ogg_path}")
    return True


def build_manifest(puke_box_dir: Path) -> list[dict]:
    """Build a manifest from date directories containing meta.json.

    Scans for directories matching YYYY-MM-DD format that contain a
    meta.json file. Returns a list of manifest entries sorted newest first.
    """
    entries = []
    for child in puke_box_dir.iterdir():
        if not child.is_dir():
            continue
        # Only consider directories matching YYYY-MM-DD format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", child.name):
            continue
        meta_path = child / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
            entries.append({
                "date": child.name,
                "description": meta.get("description", ""),
                "scale": meta.get("scale", ""),
                "root": meta.get("root", ""),
                "tempo": meta.get("tempo", 0),
            })
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping {child.name}: {e}")
            continue

    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries

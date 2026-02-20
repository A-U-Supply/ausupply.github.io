"""Post glottisdale results to a Slack channel."""

import logging
import sys
import time
from datetime import date
from pathlib import Path

from slack_sdk import WebClient

from glottisdale.types import Result
from glottisdale_slack.fetch import find_channel_id

logger = logging.getLogger(__name__)


def _log(msg: str) -> None:
    """Print to stderr so it always shows in CI logs."""
    print(f"[glottisdale-post] {msg}", file=sys.stderr, flush=True)


def _upload_with_retry(client: WebClient, max_retries: int = 3, **kwargs) -> dict:
    """Upload a file to Slack with retry on transient errors."""
    for attempt in range(max_retries):
        try:
            return client.files_upload_v2(**kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                _log(f"Upload attempt {attempt + 1} failed: {e}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def _get_thread_ts(client: WebClient, file_id: str, max_attempts: int = 5) -> tuple[str | None, str | None]:
    """Get thread_ts and channel_id from a file upload via files.info.

    Retries with increasing backoff because files_upload_v2 share info
    can take several seconds to propagate to files.info.
    """
    for attempt in range(max_attempts):
        wait = 2 * (attempt + 1)  # 2s, 4s, 6s, 8s, 10s
        time.sleep(wait)
        info = client.files_info(file=file_id)
        shares = info.get("file", {}).get("shares", {})
        for share_type in ("public", "private"):
            for ch_id, msgs in shares.get(share_type, {}).items():
                if msgs:
                    return msgs[0].get("ts"), ch_id
        _log(f"files.info attempt {attempt + 1}/{max_attempts}: no shares yet")
    return None, None


def post_results(
    token: str,
    channel: str,
    result: Result,
    sources: list[dict],
    output_dir: Path,
    _client: WebClient | None = None,
) -> None:
    """Post glottisdale results to a Slack channel.

    Uploads concatenated audio as the top-level message (MUST succeed),
    then posts clips zip as top-level and source links in thread.
    """
    _log(f"Starting post_results for channel={channel}")
    client = _client or WebClient(token=token, timeout=120)

    today = date.today().isoformat()
    summary = f":scissors: *Glottisdale* — {len(result.clips)} words from {len(sources)} source(s)"

    # Resolve channel name to ID (files_upload_v2 requires channel ID)
    channel_id = find_channel_id(client, channel) if channel.startswith("#") else channel
    if not channel_id:
        raise ValueError(f"Could not find channel: {channel}")
    _log(f"Resolved channel {channel} -> {channel_id}")

    # === WAV UPLOAD — MANDATORY, MUST SUCCEED ===
    concat_path = result.concatenated
    if not concat_path.exists():
        raise FileNotFoundError(f"Concatenated audio not found: {concat_path}")

    file_size = concat_path.stat().st_size
    _log(f"Uploading WAV: {concat_path} ({file_size} bytes)")

    resp = _upload_with_retry(
        client,
        channel=channel_id,
        file=str(concat_path),
        filename=f"glottisdale-{today}.wav",
        initial_comment=summary,
    )
    # No try/except — if this fails, the whole run fails.
    _log(f"WAV upload response keys: {list(resp.keys()) if isinstance(resp, dict) else type(resp)}")

    # Get thread_ts from the uploaded file's shares
    file_id = None
    files = resp.get("files") or []
    if not files and resp.get("file"):
        files = [resp["file"]]
    if files:
        file_id = files[0].get("id")
    _log(f"WAV file_id: {file_id}")

    thread_ts = None
    if file_id:
        thread_ts, _ = _get_thread_ts(client, file_id)
    _log(f"Thread ts: {thread_ts}")

    # Post source links in thread
    if sources and thread_ts:
        source_lines = ["*Sources:*"]
        for src in sources:
            name = src.get("name", "unknown")
            link = src.get("permalink", "")
            clip_count = len([c for c in result.clips if c.source == Path(name).stem])
            if link:
                source_lines.append(f"  - <{link}|{name}> ({clip_count} words)")
            else:
                source_lines.append(f"  - {name} ({clip_count} words)")
        try:
            client.chat_postMessage(
                channel=channel_id,
                text="\n".join(source_lines),
                thread_ts=thread_ts,
            )
            _log("Source links posted in thread")
        except Exception:
            logger.exception("Failed to post source links")
            _log("Source links failed (non-fatal)")

    # Upload clips zip in thread (after source links)
    zip_path = output_dir / "clips.zip"
    if zip_path.exists() and thread_ts:
        _log(f"Uploading zip in thread: {zip_path}")
        try:
            _upload_with_retry(
                client,
                channel=channel_id,
                file=str(zip_path),
                filename=f"glottisdale-{today}-clips.zip",
                initial_comment="Individual word clips",
                thread_ts=thread_ts,
            )
            _log("Zip uploaded successfully")
        except Exception:
            logger.exception("Failed to upload clips zip")
            _log("Zip upload failed (non-fatal)")
    elif zip_path.exists():
        _log("No thread_ts, skipping zip upload")
    else:
        _log(f"No zip found at {zip_path}")

    _log("post_results complete")

"""Post glottisdale results to a Slack channel."""

import logging
import time
from datetime import date
from pathlib import Path

from slack_sdk import WebClient

from glottisdale.types import Result
from glottisdale_slack.fetch import find_channel_id

logger = logging.getLogger(__name__)


def _upload_with_retry(client: WebClient, max_retries: int = 3, **kwargs) -> dict:
    """Upload a file to Slack with retry on transient errors."""
    for attempt in range(max_retries):
        try:
            return client.files_upload_v2(**kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning(f"Upload attempt {attempt + 1} failed: {e}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def _get_thread_ts(client: WebClient, file_id: str) -> tuple[str | None, str | None]:
    """Get thread_ts and channel_id from a file upload via files.info."""
    time.sleep(1)
    info = client.files_info(file=file_id)
    shares = info.get("file", {}).get("shares", {})
    for share_type in ("public", "private"):
        for ch_id, msgs in shares.get(share_type, {}).items():
            if msgs:
                return msgs[0].get("ts"), ch_id
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

    Uploads concatenated audio as the top-level message,
    then posts clips zip and source links in the thread.
    """
    client = _client or WebClient(token=token, timeout=120)

    today = date.today().isoformat()
    summary = f":scissors: *Glottisdale* — {len(result.clips)} words from {len(sources)} source(s)"

    # Resolve channel name to ID (files_upload_v2 requires channel ID)
    channel_id = find_channel_id(client, channel) if channel.startswith("#") else channel

    thread_ts = None

    # Upload concatenated audio as the TOP-LEVEL message (not in a thread)
    concat_path = result.concatenated
    if concat_path.exists():
        try:
            resp = _upload_with_retry(
                client,
                channel=channel_id,
                file=str(concat_path),
                filename=f"glottisdale-{today}.wav",
                initial_comment=summary,
            )
            # Get thread_ts from the uploaded file's shares
            file_id = None
            files = resp.get("files") or []
            if not files and resp.get("file"):
                files = [resp["file"]]
            if files:
                file_id = files[0].get("id")
            if file_id:
                thread_ts, _ = _get_thread_ts(client, file_id)
        except Exception:
            logger.exception("Failed to upload concatenated audio")

    # Fall back to text message if upload failed
    if not thread_ts:
        resp = client.chat_postMessage(channel=channel_id, text=summary)
        thread_ts = resp["ts"]

    # Upload clips zip as TOP-LEVEL message (not in thread)
    zip_path = output_dir / "clips.zip"
    if zip_path.exists():
        try:
            _upload_with_retry(
                client,
                channel=channel_id,
                file=str(zip_path),
                filename=f"glottisdale-{today}-clips.zip",
                initial_comment="Individual word clips",
            )
        except Exception:
            logger.exception("Failed to upload clips zip")

    # Post source links in thread
    if sources:
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
        except Exception:
            logger.exception("Failed to post source links")

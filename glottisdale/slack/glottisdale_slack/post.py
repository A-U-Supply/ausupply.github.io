"""Post glottisdale results to a Slack channel."""

import logging
from pathlib import Path

from slack_sdk import WebClient

from glottisdale.types import Result

logger = logging.getLogger(__name__)


def post_results(
    token: str,
    channel: str,
    result: Result,
    sources: list[dict],
    output_dir: Path,
    _client: WebClient | None = None,
) -> None:
    """Post glottisdale results to a Slack channel.

    Uploads concatenated audio + clips zip as the main message,
    then posts source links in a thread to keep the main post clean.
    """
    client = _client or WebClient(token=token)

    summary = f":scissors: *Glottisdale* — {len(result.clips)} words from {len(sources)} source(s)"

    # Upload concatenated audio as the main post
    concat_path = result.concatenated
    thread_ts = None
    channel_id = None

    if concat_path.exists():
        try:
            resp = client.files_upload_v2(
                channel=channel,
                file=str(concat_path),
                filename="glottisdale.wav",
                initial_comment=summary,
            )
            # Get thread_ts from the message that was created
            if resp.get("file") and resp["file"].get("shares"):
                shares = resp["file"]["shares"]
                for share_type in ("public", "private"):
                    for ch_id, msgs in shares.get(share_type, {}).items():
                        if msgs:
                            thread_ts = msgs[0].get("ts")
                            channel_id = ch_id
                            break
                    if thread_ts:
                        break
        except Exception:
            logger.exception("Failed to upload concatenated audio")

    # Fall back to a text message if upload failed
    if not thread_ts:
        resp = client.chat_postMessage(channel=channel, text=summary)
        thread_ts = resp["ts"]
        channel_id = resp["channel"]

    # Upload clips zip in thread
    zip_path = output_dir / "clips.zip"
    if zip_path.exists():
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=str(zip_path),
                filename="clips.zip",
                initial_comment="Individual word clips",
                thread_ts=thread_ts,
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

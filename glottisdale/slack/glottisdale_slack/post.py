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
    """Post concatenated audio + clips zip to a Slack channel.

    Posts a summary message, uploads concatenated.ogg to the thread,
    and uploads clips.zip as a threaded reply.
    """
    client = _client or WebClient(token=token)

    # Build summary text
    lines = [f":scissors: *Glottisdale* — {len(result.clips)} syllable clips"]
    lines.append("")
    lines.append("*Sources:*")
    for src in sources:
        name = src.get("name", "unknown")
        link = src.get("permalink", "")
        clip_count = len([c for c in result.clips if c.source == Path(name).stem])
        if link:
            lines.append(f"  - <{link}|{name}> ({clip_count} clips)")
        else:
            lines.append(f"  - {name} ({clip_count} clips)")

    summary = "\n".join(lines)

    # Post summary
    resp = client.chat_postMessage(channel=channel, text=summary)
    thread_ts = resp["ts"]
    channel_id = resp["channel"]

    # Upload concatenated audio
    concat_path = result.concatenated
    if concat_path.exists():
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=str(concat_path),
                filename="glottisdale.ogg",
                initial_comment="Concatenated syllable collage",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.exception("Failed to upload concatenated audio")

    # Upload clips zip
    zip_path = output_dir / "clips.zip"
    if zip_path.exists():
        try:
            client.files_upload_v2(
                channel=channel_id,
                file=str(zip_path),
                filename="clips.zip",
                initial_comment="Individual syllable clips",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.exception("Failed to upload clips zip")

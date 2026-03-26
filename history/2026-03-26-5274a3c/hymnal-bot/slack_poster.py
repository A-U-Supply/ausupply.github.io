"""Post Hymnal Gargler results to Slack."""
import logging
import time
from pathlib import Path

from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def format_message(
    scale: str,
    root: str,
    tempo: int,
    description: str,
    source_link: str,
    song_title: str | None = None,
) -> str:
    """Format the Slack message for posting."""
    lines = []
    if song_title:
        lines.append(f'*"{song_title}"*')
    lines.append(f":microphone: *Hymnal Gargler* — {scale} in {root} ({tempo} BPM)")
    if description:
        lines.append(f"_{description}_")
    lines.append("")
    lines.append(f"Source: <{source_link}|#midieval>")
    return "\n".join(lines)


def post_results(
    token: str,
    channel: str,
    full_mix_path: Path,
    acappella_path: Path,
    metadata: dict,
    source_link: str,
) -> None:
    """Post the two audio tracks to Slack."""
    client = WebClient(token=token)

    from slack_fetcher import find_channel_id
    channel_name = channel.lstrip("#")
    channel_id = find_channel_id(client, channel_name)
    if not channel_id:
        raise ValueError(f"Channel #{channel_name} not found")

    message = format_message(
        scale=metadata["scale"],
        root=metadata["root"],
        tempo=metadata["tempo"],
        description=metadata.get("description", ""),
        source_link=source_link,
        song_title=metadata.get("song_title"),
    )

    # Post intro message first, then upload files as thread replies
    msg_resp = client.chat_postMessage(channel=channel_id, text=message)
    thread_ts = msg_resp["ts"]

    _upload_with_retry(
        client,
        channel=channel_id,
        file=str(full_mix_path),
        filename="hymnal_gargler_mix.wav",
        title="Hymnal Gargler — Full Mix",
        thread_ts=thread_ts,
    )

    _upload_with_retry(
        client,
        channel=channel_id,
        file=str(acappella_path),
        filename="hymnal_gargler_acappella.wav",
        initial_comment=":speaking_head_in_silhouette: A cappella (vocal only)",
        title="Hymnal Gargler — A Cappella",
        thread_ts=thread_ts,
    )

    logger.info(f"Posted to #{channel_name}")


def _upload_with_retry(client: WebClient, max_retries: int = 3, **kwargs) -> dict:
    """Upload file with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return client.files_upload_v2(**kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning(f"Upload failed (attempt {attempt + 1}), retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise

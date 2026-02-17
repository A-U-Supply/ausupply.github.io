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
) -> str:
    """Format the Slack message for posting."""
    lines = [
        f":microphone: *Hymnal Gargler* — {scale} in {root} ({tempo} BPM)",
    ]
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
    )

    resp = _upload_with_retry(
        client,
        channel=channel_id,
        file=str(full_mix_path),
        filename="hymnal_gargler_mix.wav",
        initial_comment=message,
        title="Hymnal Gargler — Full Mix",
    )

    thread_ts = _get_thread_ts(client, resp)

    if thread_ts:
        try:
            _upload_with_retry(
                client,
                channel=channel_id,
                file=str(acappella_path),
                filename="hymnal_gargler_acappella.wav",
                initial_comment=":speaking_head_in_silhouette: A cappella (vocal only)",
                title="Hymnal Gargler — A Cappella",
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.warning(f"Failed to upload a cappella: {e}")

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


def _get_thread_ts(client: WebClient, upload_resp: dict) -> str | None:
    """Extract thread_ts from upload response."""
    try:
        file_obj = upload_resp.get("file", {})
        file_id = file_obj.get("id")
        if not file_id:
            return None
        info = client.files_info(file=file_id)
        shares = info.get("file", {}).get("shares", {})
        for channel_shares in shares.get("public", {}).values():
            if channel_shares:
                return channel_shares[0].get("ts")
        for channel_shares in shares.get("private", {}).values():
            if channel_shares:
                return channel_shares[0].get("ts")
    except Exception as e:
        logger.warning(f"Could not get thread_ts: {e}")
    return None

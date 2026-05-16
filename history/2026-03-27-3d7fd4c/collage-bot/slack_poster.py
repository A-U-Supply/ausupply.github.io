"""Post collaged images to Slack."""
import logging
import time
from pathlib import Path

from slack_sdk import WebClient
from slack_fetcher import find_channel_id

logger = logging.getLogger(__name__)


def post_collages(token: str, channel: str, image_paths: list[Path]) -> None:
    client = WebClient(token=token)
    channel_name = channel.lstrip("#")
    channel_id = find_channel_id(client, channel_name)
    if not channel_id:
        raise ValueError(f"Channel #{channel_name} not found")

    msg = client.chat_postMessage(channel=channel_id, text=":scissors: *collage-bot*")
    thread_ts = msg["ts"]

    for i, path in enumerate(image_paths):
        _upload_with_retry(
            client,
            channel=channel_id,
            file=str(path),
            filename=path.name,
            title=f"collage {i + 1}",
            thread_ts=thread_ts,
        )
        logger.info(f"Uploaded {path.name}")


def _upload_with_retry(client: WebClient, max_retries: int = 3, **kwargs) -> dict:
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

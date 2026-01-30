"""Slack message poster."""
import logging

from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def post_to_slack(message: str, channel: str, token: str) -> bool:
    """Post a message to Slack channel. Returns True on success."""
    try:
        client = WebClient(token=token)
        response = client.chat_postMessage(channel=channel, text=message)
        logger.info(f"Posted to {channel}: {message[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to post to Slack: {e}")
        return False

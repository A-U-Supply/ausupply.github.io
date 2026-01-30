# src/slack_fetcher.py
from dataclasses import dataclass
from slack_sdk import WebClient


@dataclass
class SlackConfig:
    token: str
    channel_id: str


def fetch_messages(config: SlackConfig, limit: int = 500) -> list[str]:
    """Fetch text messages from a Slack channel, ignoring bots and system messages."""
    client = WebClient(token=config.token)

    messages: list[str] = []
    cursor = None

    while True:
        response = client.conversations_history(
            channel=config.channel_id,
            limit=min(limit, 200),
            cursor=cursor,
        )

        for msg in response.get("messages", []):
            # Skip bot messages
            if "bot_id" in msg:
                continue
            # Skip system messages (joins, leaves, etc.)
            if "subtype" in msg:
                continue
            # Skip empty messages
            text = msg.get("text", "").strip()
            if not text:
                continue

            messages.append(text)

        # Handle pagination
        if response.get("has_more"):
            cursor = response.get("response_metadata", {}).get("next_cursor")
        else:
            break

        if len(messages) >= limit:
            break

    return messages[:limit]

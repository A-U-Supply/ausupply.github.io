# tests/test_slack_fetcher.py
import pytest
from unittest.mock import Mock, patch

from src.slack_fetcher import fetch_messages, SlackConfig


def test_fetch_messages_extracts_text():
    """Should extract text from Slack messages, ignoring bots and empty."""
    mock_client = Mock()
    mock_client.conversations_history.return_value = {
        "messages": [
            {"text": "Song Title One", "user": "U123"},
            {"text": "Song Title Two", "user": "U456"},
            {"text": "Bot message", "bot_id": "B123"},  # Should be ignored
            {"text": "", "user": "U789"},  # Empty, should be ignored
            {"subtype": "channel_join", "user": "U000"},  # System, ignored
        ],
        "has_more": False,
    }

    config = SlackConfig(token="fake-token", channel_id="C123")

    with patch("src.slack_fetcher.WebClient", return_value=mock_client):
        messages = fetch_messages(config)

    assert messages == ["Song Title One", "Song Title Two"]


def test_fetch_messages_paginates():
    """Should fetch all pages of messages."""
    mock_client = Mock()
    mock_client.conversations_history.side_effect = [
        {
            "messages": [{"text": "Page 1", "user": "U1"}],
            "has_more": True,
            "response_metadata": {"next_cursor": "cursor123"},
        },
        {
            "messages": [{"text": "Page 2", "user": "U2"}],
            "has_more": False,
        },
    ]

    config = SlackConfig(token="fake-token", channel_id="C123")

    with patch("src.slack_fetcher.WebClient", return_value=mock_client):
        messages = fetch_messages(config, limit=100)

    assert messages == ["Page 1", "Page 2"]

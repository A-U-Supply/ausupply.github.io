"""Tests for Slack poster."""
from unittest.mock import patch, MagicMock

import pytest

from src.slack_poster import post_to_slack


def test_post_to_slack_sends_message():
    """Posts message to specified channel."""
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

    with patch("src.slack_poster.WebClient", return_value=mock_client):
        result = post_to_slack(
            message="Test message",
            channel="#test",
            token="xoxb-test"
        )

    assert result is True
    mock_client.chat_postMessage.assert_called_once_with(
        channel="#test",
        text="Test message"
    )


def test_post_to_slack_handles_error():
    """Returns False on API error."""
    mock_client = MagicMock()
    mock_client.chat_postMessage.side_effect = Exception("API error")

    with patch("src.slack_poster.WebClient", return_value=mock_client):
        result = post_to_slack(
            message="Test",
            channel="#test",
            token="xoxb-test"
        )

    assert result is False

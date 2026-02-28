"""Tests for Slack video fetching."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from glottisdale_slack.fetch import (
    find_channel_id,
    find_video_messages,
    fetch_videos,
)


def test_find_channel_id():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [
            {"name": "general", "id": "C001"},
            {"name": "sample-sale", "id": "C002"},
        ],
        "response_metadata": {"next_cursor": ""},
    }
    assert find_channel_id(client, "#sample-sale") == "C002"
    assert find_channel_id(client, "sample-sale") == "C002"


def test_find_channel_id_not_found():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [{"name": "general", "id": "C001"}],
        "response_metadata": {"next_cursor": ""},
    }
    assert find_channel_id(client, "#nonexistent") is None


def test_find_video_messages():
    client = MagicMock()
    client.conversations_history.return_value = {
        "messages": [
            {
                "ts": "123.456",
                "text": "check this out",
                "files": [
                    {"mimetype": "video/mp4", "url_private_download": "https://example.com/v.mp4",
                     "name": "clip.mp4", "id": "F001"},
                ],
            },
            {
                "ts": "789.012",
                "text": "a photo",
                "files": [
                    {"mimetype": "image/png", "url_private_download": "https://example.com/i.png",
                     "name": "pic.png", "id": "F002"},
                ],
            },
            {"ts": "345.678", "text": "no files"},
        ],
        "response_metadata": {"next_cursor": ""},
    }

    videos = find_video_messages(client, "C001")
    assert len(videos) == 1
    assert videos[0]["file"]["name"] == "clip.mp4"
    assert videos[0]["ts"] == "123.456"

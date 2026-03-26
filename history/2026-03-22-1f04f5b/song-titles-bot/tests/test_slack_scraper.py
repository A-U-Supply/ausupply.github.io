"""Tests for Slack scraper — uses a fake WebClient."""
from unittest.mock import MagicMock

from src.slack_scraper import fetch_new_messages


def _make_msg(ts, text, user="U123", bot_id=None, subtype=None):
    msg = {"ts": ts, "text": text, "user": user}
    if bot_id:
        msg["bot_id"] = bot_id
    if subtype:
        msg["subtype"] = subtype
    return msg


def test_fetch_new_messages_basic():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [{"name": "song-titles", "id": "C999"}],
        "response_metadata": {"next_cursor": ""},
    }
    client.conversations_history.return_value = {
        "messages": [
            _make_msg("1710000003.000003", "third title", "U111"),
            _make_msg("1710000002.000002", "bot msg", bot_id="B999"),
            _make_msg("1710000001.000001", "first title", "U222"),
            _make_msg("1710000000.000000", "join", subtype="channel_join"),
        ],
        "has_more": False,
    }

    results = fetch_new_messages(client, channel_name="song-titles", after_ts=None)
    assert len(results) == 2
    assert results[0]["title"] == "third title"
    assert results[0]["id"] == "1710000003.000003"
    assert results[1]["title"] == "first title"


def test_fetch_new_messages_incremental():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [{"name": "song-titles", "id": "C999"}],
        "response_metadata": {"next_cursor": ""},
    }
    client.conversations_history.return_value = {
        "messages": [
            _make_msg("1710000003.000003", "new title"),
            _make_msg("1710000001.000001", "old title"),
        ],
        "has_more": False,
    }

    results = fetch_new_messages(client, channel_name="song-titles", after_ts="1710000002.000000")
    assert len(results) == 1
    assert results[0]["title"] == "new title"


def test_fetch_skips_threads():
    client = MagicMock()
    client.conversations_list.return_value = {
        "channels": [{"name": "song-titles", "id": "C999"}],
        "response_metadata": {"next_cursor": ""},
    }
    client.conversations_history.return_value = {
        "messages": [
            _make_msg("1710000003.000003", "good title"),
            {"ts": "1710000002.000002", "text": "reply", "user": "U1", "thread_ts": "1710000001.000001"},
            _make_msg("1710000001.000001", ""),
        ],
        "has_more": False,
    }

    results = fetch_new_messages(client, channel_name="song-titles", after_ts=None)
    assert len(results) == 1

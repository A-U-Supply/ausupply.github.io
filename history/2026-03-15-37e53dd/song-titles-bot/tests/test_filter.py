"""Tests for HF Inference song title filter."""
from unittest.mock import MagicMock

from src.filter import classify_messages


def _make_completion(content):
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_classify_filters_correctly():
    client = MagicMock()
    client.chat_completion.side_effect = [
        _make_completion("YES"),
        _make_completion("NO"),
        _make_completion("YES"),
    ]

    messages = [
        {"id": "1", "title": "Tip of the Fatberg"},
        {"id": "2", "title": "yeah I agree"},
        {"id": "3", "title": "sleep cartel"},
    ]

    result = classify_messages(messages, client, model="test-model")
    assert len(result) == 2
    assert result[0]["title"] == "Tip of the Fatberg"
    assert result[1]["title"] == "sleep cartel"


def test_classify_handles_whitespace():
    client = MagicMock()
    client.chat_completion.side_effect = [_make_completion("  Yes.  "), _make_completion("  no  ")]

    messages = [{"id": "1", "title": "good"}, {"id": "2", "title": "bad"}]
    result = classify_messages(messages, client, model="test")
    assert len(result) == 1


def test_classify_empty_input():
    client = MagicMock()
    result = classify_messages([], client, model="test")
    assert result == []
    assert client.chat_completion.call_count == 0

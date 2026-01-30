# tests/test_filter.py
import pytest
from unittest.mock import Mock, patch

from src.filter import filter_song_titles, FilterConfig


def test_filter_identifies_song_titles():
    """Should keep messages classified as song titles."""
    mock_response = Mock()
    mock_response.json.side_effect = [
        {"response": "YES"},
        {"response": "NO"},
        {"response": "YES"},
    ]
    mock_response.raise_for_status = Mock()

    messages = ["Dust Bobbles", "yo that's great", "Even Sky Is Blue"]
    config = FilterConfig(model="llama3", base_url="http://localhost:11434")

    with patch("src.filter.requests.post", return_value=mock_response):
        result = filter_song_titles(messages, config)

    assert result == ["Dust Bobbles", "Even Sky Is Blue"]


def test_filter_handles_lowercase_responses():
    """Should handle yes/no in any case."""
    mock_response = Mock()
    mock_response.json.side_effect = [
        {"response": "yes"},
        {"response": "Yes"},
        {"response": "no"},
    ]
    mock_response.raise_for_status = Mock()

    messages = ["Title A", "Title B", "not a title"]
    config = FilterConfig(model="llama3", base_url="http://localhost:11434")

    with patch("src.filter.requests.post", return_value=mock_response):
        result = filter_song_titles(messages, config)

    assert result == ["Title A", "Title B"]

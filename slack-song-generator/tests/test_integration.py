# tests/test_integration.py
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.slack_fetcher import fetch_messages, SlackConfig
from src.filter import filter_song_titles, FilterConfig
from src.generator import generate_html, GeneratorConfig
from src.cache import save_titles, load_titles


def test_full_pipeline(tmp_path):
    """Test the full pipeline from Slack to HTML."""
    # Mock Slack response
    mock_client = Mock()
    mock_client.conversations_history.return_value = {
        "messages": [
            {"text": "Dust Bobbles", "user": "U1"},
            {"text": "Even Sky Is Blue", "user": "U2"},
            {"text": "yo check this out", "user": "U3"},
            {"text": "Mind Xor Pees And Queues", "user": "U4"},
        ],
        "has_more": False,
    }

    # Mock Ollama responses
    mock_ollama = Mock()
    mock_ollama.json.side_effect = [
        {"response": "YES"},  # Dust Bobbles
        {"response": "YES"},  # Even Sky Is Blue
        {"response": "NO"},   # yo check this out
        {"response": "YES"},  # Mind Xor Pees And Queues
    ]
    mock_ollama.raise_for_status = Mock()

    # Run pipeline
    with patch("src.slack_fetcher.WebClient", return_value=mock_client):
        slack_config = SlackConfig(token="fake", channel_id="C123")
        messages = fetch_messages(slack_config)

    assert len(messages) == 4

    with patch("src.filter.requests.post", return_value=mock_ollama):
        filter_config = FilterConfig(model="llama3")
        titles = filter_song_titles(messages, filter_config)

    assert titles == ["Dust Bobbles", "Even Sky Is Blue", "Mind Xor Pees And Queues"]

    # Cache
    cache_path = tmp_path / "titles.json"
    save_titles(titles, cache_path)
    loaded = load_titles(cache_path)
    assert loaded == titles

    # Generate HTML
    output_path = tmp_path / "output.html"
    gen_config = GeneratorConfig(seed=42)
    generate_html(titles, gen_config, output_path)

    html = output_path.read_text()
    assert "Dust Bobbles" in html
    assert "Even Sky Is Blue" in html
    assert "Mind Xor Pees And Queues" in html
    assert "SONG TITLE LIBRARY" in html

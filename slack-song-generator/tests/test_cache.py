import pytest
import json
from pathlib import Path

from src.cache import save_titles, load_titles


def test_save_and_load_titles(tmp_path):
    """Should save and load titles from JSON."""
    cache_file = tmp_path / "titles.json"
    titles = ["Song One", "Song Two", "Song Three"]

    save_titles(titles, cache_file)
    loaded = load_titles(cache_file)

    assert loaded == titles


def test_load_titles_returns_empty_if_missing(tmp_path):
    """Should return empty list if cache file doesn't exist."""
    cache_file = tmp_path / "nonexistent.json"

    loaded = load_titles(cache_file)

    assert loaded == []

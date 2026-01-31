"""Tests for news scraper."""
from unittest.mock import patch, MagicMock

import pytest

from src.scraper import scrape_source, scrape_all_sources, SCRAPERS


def test_scrape_source_returns_headlines():
    """Scraper returns list of headline strings."""
    mock_response = MagicMock()
    mock_response.text = "<html><h3>This is a test headline that is long enough</h3><h3>Another story headline here</h3></html>"
    mock_response.raise_for_status = MagicMock()

    with patch("src.scraper.requests.get", return_value=mock_response):
        headlines = scrape_source("reuters")

    assert isinstance(headlines, list)
    assert len(headlines) > 0
    assert all(isinstance(h, str) for h in headlines)


def test_scrape_source_handles_failure():
    """Scraper returns empty list on failure, doesn't crash."""
    with patch("src.scraper.requests.get", side_effect=Exception("Network error")):
        headlines = scrape_source("reuters")

    assert headlines == []


def test_scrape_all_sources_aggregates():
    """Scrape all combines headlines from multiple sources."""
    with patch("src.scraper.scrape_source") as mock_scrape:
        mock_scrape.side_effect = [
            ["Headline 1", "Headline 2"],
            ["Headline 3"],
            [],  # One source fails
        ]
        headlines = scrape_all_sources(["reuters", "bbc", "cnn"])

    assert len(headlines) == 3
    assert "Headline 1" in headlines


def test_all_sources_have_scrapers():
    """Every configured source has a scraper function."""
    default_sources = ["reuters", "foxnews", "cnn", "bbc", "ft", "npr", "guardian", "breitbart"]
    for source in default_sources:
        assert source in SCRAPERS, f"Missing scraper for {source}"

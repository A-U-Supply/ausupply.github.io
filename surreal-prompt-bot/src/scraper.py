"""News headline scrapers for various sources."""
import logging
from typing import Callable

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SurrealPromptBot/1.0)"
}


def _scrape_reuters() -> list[str]:
    """Scrape Reuters homepage headlines."""
    resp = requests.get("https://www.reuters.com/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h3, [data-testid='Heading']")[:10]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


def _scrape_bbc() -> list[str]:
    """Scrape BBC News homepage headlines."""
    resp = requests.get("https://www.bbc.com/news", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h2, h3")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 15:
            headlines.append(text)
    return headlines[:5]


def _scrape_cnn() -> list[str]:
    """Scrape CNN homepage headlines."""
    resp = requests.get("https://www.cnn.com/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("span.container__headline-text, h3")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


def _scrape_foxnews() -> list[str]:
    """Scrape Fox News homepage headlines."""
    resp = requests.get("https://www.foxnews.com/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h2.title, h3.title, .title a")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


def _scrape_ft() -> list[str]:
    """Scrape Financial Times homepage headlines."""
    resp = requests.get("https://www.ft.com/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("a.js-teaser-heading-link, h3")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


def _scrape_npr() -> list[str]:
    """Scrape NPR homepage headlines."""
    resp = requests.get("https://www.npr.org/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h2.title, h3.title, .title a, .story-text a")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


def _scrape_guardian() -> list[str]:
    """Scrape The Guardian homepage headlines."""
    resp = requests.get("https://www.theguardian.com/us", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h3, .fc-item__title")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


def _scrape_breitbart() -> list[str]:
    """Scrape Breitbart homepage headlines."""
    resp = requests.get("https://www.breitbart.com/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h2 a, h3 a, .title a")[:15]:
        text = el.get_text(strip=True)
        if text and len(text) > 10:
            headlines.append(text)
    return headlines[:5]


SCRAPERS: dict[str, Callable[[], list[str]]] = {
    "reuters": _scrape_reuters,
    "bbc": _scrape_bbc,
    "cnn": _scrape_cnn,
    "foxnews": _scrape_foxnews,
    "ft": _scrape_ft,
    "npr": _scrape_npr,
    "guardian": _scrape_guardian,
    "breitbart": _scrape_breitbart,
}


def scrape_source(source: str) -> list[str]:
    """Scrape headlines from a single source. Returns empty list on failure."""
    if source not in SCRAPERS:
        logger.warning(f"Unknown source: {source}")
        return []

    try:
        return SCRAPERS[source]()
    except Exception as e:
        logger.warning(f"Failed to scrape {source}: {e}")
        return []


def scrape_all_sources(sources: list[str]) -> list[str]:
    """Scrape headlines from all specified sources."""
    all_headlines = []
    for source in sources:
        headlines = scrape_source(source)
        logger.info(f"Scraped {len(headlines)} headlines from {source}")
        all_headlines.extend(headlines)
    return all_headlines

# Surreal Prompt Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python bot that scrapes news headlines, mixes with random artistic inspirations, generates surrealist drawing prompts via Groq API, and posts daily to Slack.

**Architecture:** CLI script with modular components (scraper, sampler, generator, poster) coordinated by main entrypoint. YAML config with CLI overrides. GitHub Actions for daily scheduling.

**Tech Stack:** Python 3.11+, requests, beautifulsoup4, groq, slack-sdk, pyyaml, argparse

---

### Task 1: Project Scaffolding

**Files:**
- Create: `surreal-prompt-bot/bot.py`
- Create: `surreal-prompt-bot/requirements.txt`
- Create: `surreal-prompt-bot/config.yaml`
- Create: `surreal-prompt-bot/inspirations.txt`
- Create: `surreal-prompt-bot/src/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p surreal-prompt-bot/src
touch surreal-prompt-bot/src/__init__.py
```

**Step 2: Create requirements.txt**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
groq>=0.4.0
slack-sdk>=3.27.0
pyyaml>=6.0.0
```

**Step 3: Create default config.yaml**

```yaml
slack:
  channel: "#drawma"

prompt:
  temperature: 1.0
  model: llama-3.1-8b-instant
  max_headlines: 10

inspirations:
  file: inspirations.txt
  pick_count: 2

sources:
  - reuters
  - foxnews
  - cnn
  - bbc
  - ft
  - bloomberg
  - guardian
  - breitbart
```

**Step 4: Create starter inspirations.txt**

```
corporate memphis art style
1990s clip art energy
deep fried meme aesthetic
renaissance painting but wrong
vaporwave capitalism
classified government document
children's educational poster
infomercial accident
liminal space vibes
wikihow illustration gone wrong
stock photo nightmare
brutalist architecture mood
Y2K web design nostalgia
failed AI art generation
conspiracy corkboard aesthetic
```

**Step 5: Create bot.py skeleton**

```python
#!/usr/bin/env python3
"""Surreal Prompt Bot - Daily surrealist drawing prompts from news headlines."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate surreal drawing prompts from news")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't post to Slack")
    parser.add_argument("--channel", help="Override Slack channel")
    parser.add_argument("--temperature", type=float, help="LLM temperature (0.0-2.0)")
    parser.add_argument("--sources", help="Comma-separated list of news sources")
    parser.add_argument("--no-inspirations", action="store_true", help="Skip inspiration file")
    parser.add_argument("--config", default="config.yaml", help="Config file path")

    args = parser.parse_args()

    print("Surreal Prompt Bot - Not yet implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 6: Install dependencies**

```bash
cd surreal-prompt-bot && pip install -r requirements.txt
```

**Step 7: Verify skeleton runs**

```bash
python bot.py --help
python bot.py --dry-run
```

Expected: Help text displays, dry-run prints "Not yet implemented"

**Step 8: Commit**

```bash
git add surreal-prompt-bot/
git commit -m "feat: scaffold surreal-prompt-bot project structure"
```

---

### Task 2: Config Loader

**Files:**
- Create: `surreal-prompt-bot/src/config.py`
- Create: `surreal-prompt-bot/tests/__init__.py`
- Create: `surreal-prompt-bot/tests/test_config.py`

**Step 1: Write the failing test**

```python
"""Tests for config loader."""
import tempfile
from pathlib import Path

import pytest

from src.config import load_config, merge_cli_args


def test_load_config_defaults():
    """Config has sensible defaults when file missing."""
    config = load_config(Path("/nonexistent/config.yaml"))
    assert config["slack"]["channel"] == "#drawma"
    assert config["prompt"]["model"] == "llama-3.1-8b-instant"


def test_load_config_from_file():
    """Config loads values from YAML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("slack:\n  channel: '#test-channel'\n")
        f.flush()
        config = load_config(Path(f.name))
    assert config["slack"]["channel"] == "#test-channel"


def test_merge_cli_args_overrides():
    """CLI args override config values."""
    config = {"slack": {"channel": "#drawma"}, "prompt": {"temperature": 1.0}}

    class Args:
        channel = "#override"
        temperature = 1.5
        sources = None
        no_inspirations = False

    merged = merge_cli_args(config, Args())
    assert merged["slack"]["channel"] == "#override"
    assert merged["prompt"]["temperature"] == 1.5
```

**Step 2: Run test to verify it fails**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_config.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.config'"

**Step 3: Write minimal implementation**

```python
"""Configuration loader with YAML support and CLI overrides."""
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = {
    "slack": {
        "channel": "#drawma",
    },
    "prompt": {
        "temperature": 1.0,
        "model": "llama-3.1-8b-instant",
        "max_headlines": 10,
    },
    "inspirations": {
        "file": "inspirations.txt",
        "pick_count": 2,
    },
    "sources": [
        "reuters", "foxnews", "cnn", "bbc",
        "ft", "bloomberg", "guardian", "breitbart"
    ],
}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load config from YAML file, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()

    if config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_cli_args(config: dict[str, Any], args) -> dict[str, Any]:
    """Merge CLI arguments into config, overriding where specified."""
    if args.channel:
        config["slack"]["channel"] = args.channel
    if args.temperature is not None:
        config["prompt"]["temperature"] = args.temperature
    if args.sources:
        config["sources"] = args.sources.split(",")
    if args.no_inspirations:
        config["inspirations"]["pick_count"] = 0
    return config
```

**Step 4: Run test to verify it passes**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_config.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add surreal-prompt-bot/src/config.py surreal-prompt-bot/tests/
git commit -m "feat: add config loader with YAML and CLI support"
```

---

### Task 3: News Scraper

**Files:**
- Create: `surreal-prompt-bot/src/scraper.py`
- Create: `surreal-prompt-bot/tests/test_scraper.py`

**Step 1: Write the failing test**

```python
"""Tests for news scraper."""
from unittest.mock import patch, MagicMock

import pytest

from src.scraper import scrape_source, scrape_all_sources, SCRAPERS


def test_scrape_source_returns_headlines():
    """Scraper returns list of headline strings."""
    mock_response = MagicMock()
    mock_response.text = "<html><h2>Test Headline One</h2><h2>Another Story</h2></html>"
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
    default_sources = ["reuters", "foxnews", "cnn", "bbc", "ft", "bloomberg", "guardian", "breitbart"]
    for source in default_sources:
        assert source in SCRAPERS, f"Missing scraper for {source}"
```

**Step 2: Run test to verify it fails**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_scraper.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.scraper'"

**Step 3: Write minimal implementation**

```python
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


def _scrape_bloomberg() -> list[str]:
    """Scrape Bloomberg homepage headlines."""
    resp = requests.get("https://www.bloomberg.com/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    headlines = []
    for el in soup.select("h3, [data-component='headline']")[:15]:
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
    "bloomberg": _scrape_bloomberg,
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
```

**Step 4: Run test to verify it passes**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_scraper.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add surreal-prompt-bot/src/scraper.py surreal-prompt-bot/tests/test_scraper.py
git commit -m "feat: add news scraper for 8 sources"
```

---

### Task 4: Inspiration Sampler

**Files:**
- Create: `surreal-prompt-bot/src/sampler.py`
- Create: `surreal-prompt-bot/tests/test_sampler.py`

**Step 1: Write the failing test**

```python
"""Tests for inspiration sampler."""
import tempfile
from pathlib import Path

import pytest

from src.sampler import load_inspirations, sample_inspirations


def test_load_inspirations_from_file():
    """Loads lines from text file, strips whitespace."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line one\n  line two  \n\nline three\n")
        f.flush()
        inspirations = load_inspirations(Path(f.name))

    assert inspirations == ["line one", "line two", "line three"]


def test_load_inspirations_missing_file():
    """Returns empty list for missing file."""
    inspirations = load_inspirations(Path("/nonexistent/file.txt"))
    assert inspirations == []


def test_sample_inspirations_picks_n():
    """Samples requested number of items."""
    items = ["a", "b", "c", "d", "e"]
    sampled = sample_inspirations(items, count=2)
    assert len(sampled) == 2
    assert all(s in items for s in sampled)


def test_sample_inspirations_handles_small_list():
    """Returns all items if fewer than requested."""
    items = ["a", "b"]
    sampled = sample_inspirations(items, count=5)
    assert len(sampled) == 2


def test_sample_inspirations_zero_count():
    """Returns empty list for zero count."""
    sampled = sample_inspirations(["a", "b", "c"], count=0)
    assert sampled == []
```

**Step 2: Run test to verify it fails**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_sampler.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.sampler'"

**Step 3: Write minimal implementation**

```python
"""Inspiration sampler - picks random artistic inspirations from text file."""
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


def load_inspirations(file_path: Path) -> list[str]:
    """Load inspirations from text file, one per line."""
    if not file_path.exists():
        logger.warning(f"Inspirations file not found: {file_path}")
        return []

    with open(file_path) as f:
        lines = [line.strip() for line in f if line.strip()]

    logger.info(f"Loaded {len(lines)} inspirations from {file_path}")
    return lines


def sample_inspirations(inspirations: list[str], count: int) -> list[str]:
    """Randomly sample N inspirations from list."""
    if count <= 0:
        return []

    if len(inspirations) <= count:
        return inspirations[:]

    return random.sample(inspirations, count)
```

**Step 4: Run test to verify it passes**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_sampler.py -v
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add surreal-prompt-bot/src/sampler.py surreal-prompt-bot/tests/test_sampler.py
git commit -m "feat: add inspiration sampler"
```

---

### Task 5: Prompt Generator (Groq)

**Files:**
- Create: `surreal-prompt-bot/src/generator.py`
- Create: `surreal-prompt-bot/tests/test_generator.py`

**Step 1: Write the failing test**

```python
"""Tests for prompt generator."""
from unittest.mock import patch, MagicMock

import pytest

from src.generator import generate_prompt, build_llm_prompt


def test_build_llm_prompt_includes_headlines():
    """LLM prompt contains all headlines."""
    headlines = ["Economy crashes", "Aliens land"]
    inspirations = ["vaporwave"]

    prompt = build_llm_prompt(headlines, inspirations)

    assert "Economy crashes" in prompt
    assert "Aliens land" in prompt
    assert "vaporwave" in prompt


def test_build_llm_prompt_without_inspirations():
    """LLM prompt works without inspirations."""
    headlines = ["Breaking news"]

    prompt = build_llm_prompt(headlines, [])

    assert "Breaking news" in prompt
    assert "Artistic inspiration" not in prompt


def test_generate_prompt_calls_groq():
    """Generator calls Groq API and returns response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test prompt output"))]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("src.generator.Groq", return_value=mock_client):
        result = generate_prompt(
            headlines=["Test headline"],
            inspirations=["test style"],
            model="llama-3.1-8b-instant",
            temperature=1.0,
            api_key="test-key"
        )

    assert result == "Test prompt output"
    mock_client.chat.completions.create.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_generator.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.generator'"

**Step 3: Write minimal implementation**

```python
"""Prompt generator using Groq API."""
import logging

from groq import Groq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a surrealist artist with severe internet brain rot.
Generate a single drawing prompt in the style of a surreal, unhinged headline.
Include 1-3 emojis. One sentence. Do not explain it."""


def build_llm_prompt(headlines: list[str], inspirations: list[str]) -> str:
    """Build the prompt to send to the LLM."""
    parts = ["Today's news headlines:"]
    for headline in headlines:
        parts.append(f"- {headline}")

    if inspirations:
        parts.append("\nArtistic inspiration for today:")
        for insp in inspirations:
            parts.append(f"- {insp}")

    return "\n".join(parts)


def generate_prompt(
    headlines: list[str],
    inspirations: list[str],
    model: str,
    temperature: float,
    api_key: str,
) -> str:
    """Generate a surreal prompt using Groq API."""
    client = Groq(api_key=api_key)

    user_prompt = build_llm_prompt(headlines, inspirations)
    logger.debug(f"LLM prompt:\n{user_prompt}")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=150,
    )

    result = response.choices[0].message.content.strip()
    logger.info(f"Generated prompt: {result}")
    return result
```

**Step 4: Run test to verify it passes**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_generator.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add surreal-prompt-bot/src/generator.py surreal-prompt-bot/tests/test_generator.py
git commit -m "feat: add Groq-based prompt generator"
```

---

### Task 6: Slack Poster

**Files:**
- Create: `surreal-prompt-bot/src/slack_poster.py`
- Create: `surreal-prompt-bot/tests/test_slack_poster.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_slack_poster.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.slack_poster'"

**Step 3: Write minimal implementation**

```python
"""Slack message poster."""
import logging

from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def post_to_slack(message: str, channel: str, token: str) -> bool:
    """Post a message to Slack channel. Returns True on success."""
    try:
        client = WebClient(token=token)
        response = client.chat_postMessage(channel=channel, text=message)
        logger.info(f"Posted to {channel}: {message[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to post to Slack: {e}")
        return False
```

**Step 4: Run test to verify it passes**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_slack_poster.py -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add surreal-prompt-bot/src/slack_poster.py surreal-prompt-bot/tests/test_slack_poster.py
git commit -m "feat: add Slack poster"
```

---

### Task 7: Wire Up Main Bot

**Files:**
- Modify: `surreal-prompt-bot/bot.py`
- Create: `surreal-prompt-bot/tests/test_bot.py`

**Step 1: Write the failing test**

```python
"""Tests for main bot entrypoint."""
from unittest.mock import patch, MagicMock
import sys

import pytest


def test_bot_dry_run_does_not_post():
    """Dry run generates prompt but doesn't post to Slack."""
    with patch("src.scraper.scrape_all_sources", return_value=["Test headline"]), \
         patch("src.sampler.load_inspirations", return_value=["test style"]), \
         patch("src.sampler.sample_inspirations", return_value=["test style"]), \
         patch("src.generator.generate_prompt", return_value="Test prompt"), \
         patch("src.slack_poster.post_to_slack") as mock_post, \
         patch.dict("os.environ", {"GROQ_API_KEY": "test"}):

        # Import after patching
        from bot import run_bot

        class Args:
            dry_run = True
            channel = None
            temperature = None
            sources = None
            no_inspirations = False
            config = "config.yaml"

        result = run_bot(Args())

        mock_post.assert_not_called()
        assert result == 0


def test_bot_posts_on_success():
    """Bot posts generated prompt to Slack."""
    with patch("src.scraper.scrape_all_sources", return_value=["Test headline"]), \
         patch("src.sampler.load_inspirations", return_value=["test style"]), \
         patch("src.sampler.sample_inspirations", return_value=["test style"]), \
         patch("src.generator.generate_prompt", return_value="Test prompt"), \
         patch("src.slack_poster.post_to_slack", return_value=True) as mock_post, \
         patch.dict("os.environ", {"GROQ_API_KEY": "test", "SLACK_BOT_TOKEN": "xoxb-test"}):

        from bot import run_bot

        class Args:
            dry_run = False
            channel = "#test"
            temperature = None
            sources = None
            no_inspirations = False
            config = "config.yaml"

        result = run_bot(Args())

        mock_post.assert_called_once()
        assert result == 0
```

**Step 2: Run test to verify it fails**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_bot.py -v
```

Expected: FAIL with "cannot import name 'run_bot' from 'bot'"

**Step 3: Write implementation**

Replace `bot.py` with:

```python
#!/usr/bin/env python3
"""Surreal Prompt Bot - Daily surrealist drawing prompts from news headlines."""

import argparse
import logging
import os
import random
import sys
from pathlib import Path

from src.config import load_config, merge_cli_args
from src.scraper import scrape_all_sources
from src.sampler import load_inspirations, sample_inspirations
from src.generator import generate_prompt
from src.slack_poster import post_to_slack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_bot(args) -> int:
    """Main bot logic. Returns exit code."""
    # Load config
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config
    config = load_config(config_path)
    config = merge_cli_args(config, args)

    # Get API keys from environment
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("GROQ_API_KEY environment variable not set")
        return 1

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token and not args.dry_run:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    # Scrape headlines
    logger.info(f"Scraping headlines from {len(config['sources'])} sources...")
    headlines = scrape_all_sources(config["sources"])

    if not headlines:
        logger.error("No headlines scraped from any source")
        return 1

    # Pick random subset of headlines
    max_headlines = config["prompt"]["max_headlines"]
    if len(headlines) > max_headlines:
        headlines = random.sample(headlines, max_headlines)

    logger.info(f"Using {len(headlines)} headlines")

    # Load and sample inspirations
    inspirations = []
    if config["inspirations"]["pick_count"] > 0:
        insp_path = script_dir / config["inspirations"]["file"]
        all_inspirations = load_inspirations(insp_path)
        inspirations = sample_inspirations(
            all_inspirations,
            config["inspirations"]["pick_count"]
        )
        logger.info(f"Using inspirations: {inspirations}")

    # Generate prompt
    logger.info("Generating surreal prompt...")
    prompt = generate_prompt(
        headlines=headlines,
        inspirations=inspirations,
        model=config["prompt"]["model"],
        temperature=config["prompt"]["temperature"],
        api_key=groq_api_key,
    )

    print(f"\n{'='*60}")
    print(f"Generated prompt:\n{prompt}")
    print(f"{'='*60}\n")

    # Post to Slack (unless dry run)
    if args.dry_run:
        logger.info("Dry run - not posting to Slack")
        return 0

    channel = config["slack"]["channel"]
    logger.info(f"Posting to Slack channel {channel}...")

    if post_to_slack(prompt, channel, slack_token):
        logger.info("Successfully posted to Slack!")
        return 0
    else:
        logger.error("Failed to post to Slack")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Generate surreal drawing prompts from news headlines"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate prompt but don't post to Slack"
    )
    parser.add_argument(
        "--channel",
        help="Override Slack channel (default: #drawma)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="LLM temperature 0.0-2.0 (default: 1.0)"
    )
    parser.add_argument(
        "--sources",
        help="Comma-separated list of news sources"
    )
    parser.add_argument(
        "--no-inspirations",
        action="store_true",
        help="Skip inspiration file"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Config file path (default: config.yaml)"
    )

    args = parser.parse_args()
    return run_bot(args)


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run test to verify it passes**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_bot.py -v
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add surreal-prompt-bot/bot.py surreal-prompt-bot/tests/test_bot.py
git commit -m "feat: wire up main bot with all components"
```

---

### Task 8: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/daily-prompt.yml`

**Step 1: Create workflows directory**

```bash
mkdir -p .github/workflows
```

**Step 2: Create workflow file**

```yaml
name: Daily Surreal Prompt

on:
  schedule:
    # 7am PT = 3pm UTC (during PST)
    # 7am PT = 2pm UTC (during PDT)
    # Using 3pm UTC for consistency
    - cron: '0 15 * * *'
  workflow_dispatch:  # Manual trigger button

jobs:
  post-prompt:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r surreal-prompt-bot/requirements.txt

      - name: Run bot
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python surreal-prompt-bot/bot.py
```

**Step 3: Verify workflow syntax**

```bash
# Check YAML is valid
python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-prompt.yml'))"
```

Expected: No output (valid YAML)

**Step 4: Commit**

```bash
git add .github/workflows/daily-prompt.yml
git commit -m "feat: add GitHub Actions workflow for daily posting"
```

---

### Task 9: Integration Test & Manual Run

**Files:**
- None (testing existing code)

**Step 1: Run all unit tests**

```bash
cd surreal-prompt-bot && python -m pytest tests/ -v
```

Expected: All tests pass

**Step 2: Test dry run locally**

```bash
cd surreal-prompt-bot
export GROQ_API_KEY="your-groq-api-key"  # Get from https://console.groq.com
python bot.py --dry-run
```

Expected: Headlines scraped, prompt generated, "Dry run - not posting to Slack"

**Step 3: Test with specific sources**

```bash
python bot.py --dry-run --sources reuters,bbc
```

Expected: Only 2 sources scraped

**Step 4: Test full run (posts to Slack)**

```bash
export SLACK_BOT_TOKEN="xoxb-your-token"
python bot.py --channel "#test-channel"
```

Expected: Prompt posted to Slack test channel

**Step 5: Commit any fixes from integration testing**

```bash
git add -A && git commit -m "fix: integration test fixes" || echo "No fixes needed"
```

---

### Task 10: Final Cleanup & Documentation

**Files:**
- Create: `surreal-prompt-bot/README.md`

**Step 1: Create README**

```markdown
# Surreal Prompt Bot

A daily Slack bot that generates surrealist drawing prompts inspired by news headlines.

## How It Works

1. Scrapes headlines from diverse news sources (FT, Fox News, CNN, Reuters, BBC, etc.)
2. Picks random artistic inspirations from `inspirations.txt`
3. Feeds both to Groq's free Llama API
4. Posts a surreal headline-style drawing prompt to Slack

## Setup

### 1. Get API Keys

- **Groq**: Free at https://console.groq.com
- **Slack**: Create app at https://api.slack.com/apps with `chat:write` scope

### 2. Configure GitHub Secrets

In your repo settings, add:
- `GROQ_API_KEY`
- `SLACK_BOT_TOKEN`

### 3. Invite Bot to Channel

Invite your Slack bot to `#drawma` (or your chosen channel).

## Local Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="gsk_..."
export SLACK_BOT_TOKEN="xoxb-..."

# Dry run (no Slack posting)
python bot.py --dry-run

# Post to default channel (#drawma)
python bot.py

# Post to different channel
python bot.py --channel "#test"

# Use specific sources only
python bot.py --sources reuters,bbc

# Skip inspirations
python bot.py --no-inspirations

# Adjust creativity
python bot.py --temperature 1.5
```

## Configuration

Edit `config.yaml` to change defaults:

```yaml
slack:
  channel: "#drawma"

prompt:
  temperature: 1.0
  model: llama-3.1-8b-instant
  max_headlines: 10

inspirations:
  file: inspirations.txt
  pick_count: 2

sources:
  - reuters
  - foxnews
  - cnn
  - bbc
  - ft
  - bloomberg
  - guardian
  - breitbart
```

## Adding Inspirations

Edit `inspirations.txt`, one per line:

```
corporate memphis art style
deep fried meme aesthetic
vaporwave capitalism
```

## Example Outputs

- "📉 Local Fish Achieves Enlightenment Through Fiscal Policy, Refuses Comment 🐟"
- "🏛️ The Moon Files For Bankruptcy While Clouds Hold Emergency Session 💨"
- "Breaking: Your Childhood Bedroom Now A Subsidiary Of Feelings Inc. 🛏️"
```

**Step 2: Run final test suite**

```bash
cd surreal-prompt-bot && python -m pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 3: Final commit**

```bash
git add surreal-prompt-bot/README.md
git commit -m "docs: add README for surreal-prompt-bot"
```

---

## Post-Implementation

After all tasks complete:

1. **Merge to main**: Use `superpowers:finishing-a-development-branch`
2. **Add GitHub Secrets**: GROQ_API_KEY and SLACK_BOT_TOKEN in repo settings
3. **Test workflow**: Use "Run workflow" button in GitHub Actions
4. **Monitor**: Check Actions tab for daily runs

## Secrets Required

| Secret | Where to get |
|--------|--------------|
| `GROQ_API_KEY` | https://console.groq.com (free tier) |
| `SLACK_BOT_TOKEN` | Slack app with `chat:write` scope |

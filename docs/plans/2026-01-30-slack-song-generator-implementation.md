# Slack Song Title Generator - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI that fetches song titles from Slack, filters with Ollama, and generates chaotic geocities-style HTML.

**Architecture:** Three modules (slack_fetcher, filter, generator) wired together by a CLI entrypoint. Jinja2 templates for HTML. JSON cache for filtered titles.

**Tech Stack:** Python 3.11+, slack-sdk, requests, jinja2, python-dotenv, uv

---

## Task 1: Project Scaffolding

**Files:**
- Create: `slack-song-generator/pyproject.toml`
- Create: `slack-song-generator/.env.example`
- Create: `slack-song-generator/src/__init__.py`
- Create: `slack-song-generator/src/templates/.gitkeep`
- Create: `slack-song-generator/cache/.gitkeep`

**Step 1: Create project directory structure**

```bash
mkdir -p slack-song-generator/src/templates
mkdir -p slack-song-generator/cache
mkdir -p slack-song-generator/tests
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "slack-song-generator"
version = "0.1.0"
description = "Generate chaotic geocities-style pages from Slack song titles"
requires-python = ">=3.11"
dependencies = [
    "slack-sdk>=3.27.0",
    "requests>=2.31.0",
    "jinja2>=3.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
]

[project.scripts]
generate-song-page = "src.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 3: Create .env.example**

```
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL_ID=C0XXXXXXX
OLLAMA_MODEL=llama3
```

**Step 4: Create empty __init__.py files**

```bash
touch slack-song-generator/src/__init__.py
touch slack-song-generator/src/templates/.gitkeep
touch slack-song-generator/cache/.gitkeep
touch slack-song-generator/tests/__init__.py
```

**Step 5: Initialize with uv and commit**

```bash
cd slack-song-generator
uv sync
git add .
git commit -m "feat: scaffold slack-song-generator project"
```

---

## Task 2: Slack Fetcher Module

**Files:**
- Create: `slack-song-generator/src/slack_fetcher.py`
- Create: `slack-song-generator/tests/test_slack_fetcher.py`

**Step 1: Write the failing test**

```python
# tests/test_slack_fetcher.py
import pytest
from unittest.mock import Mock, patch

from src.slack_fetcher import fetch_messages, SlackConfig


def test_fetch_messages_extracts_text():
    """Should extract text from Slack messages, ignoring bots and empty."""
    mock_client = Mock()
    mock_client.conversations_history.return_value = {
        "messages": [
            {"text": "Song Title One", "user": "U123"},
            {"text": "Song Title Two", "user": "U456"},
            {"text": "Bot message", "bot_id": "B123"},  # Should be ignored
            {"text": "", "user": "U789"},  # Empty, should be ignored
            {"subtype": "channel_join", "user": "U000"},  # System, ignored
        ],
        "has_more": False,
    }

    config = SlackConfig(token="fake-token", channel_id="C123")

    with patch("src.slack_fetcher.WebClient", return_value=mock_client):
        messages = fetch_messages(config)

    assert messages == ["Song Title One", "Song Title Two"]


def test_fetch_messages_paginates():
    """Should fetch all pages of messages."""
    mock_client = Mock()
    mock_client.conversations_history.side_effect = [
        {
            "messages": [{"text": "Page 1", "user": "U1"}],
            "has_more": True,
            "response_metadata": {"next_cursor": "cursor123"},
        },
        {
            "messages": [{"text": "Page 2", "user": "U2"}],
            "has_more": False,
        },
    ]

    config = SlackConfig(token="fake-token", channel_id="C123")

    with patch("src.slack_fetcher.WebClient", return_value=mock_client):
        messages = fetch_messages(config, limit=100)

    assert messages == ["Page 1", "Page 2"]
```

**Step 2: Run test to verify it fails**

```bash
cd slack-song-generator
uv run pytest tests/test_slack_fetcher.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.slack_fetcher'`

**Step 3: Write minimal implementation**

```python
# src/slack_fetcher.py
from dataclasses import dataclass
from slack_sdk import WebClient


@dataclass
class SlackConfig:
    token: str
    channel_id: str


def fetch_messages(config: SlackConfig, limit: int = 500) -> list[str]:
    """Fetch text messages from a Slack channel, ignoring bots and system messages."""
    client = WebClient(token=config.token)

    messages: list[str] = []
    cursor = None

    while True:
        response = client.conversations_history(
            channel=config.channel_id,
            limit=min(limit, 200),
            cursor=cursor,
        )

        for msg in response.get("messages", []):
            # Skip bot messages
            if "bot_id" in msg:
                continue
            # Skip system messages (joins, leaves, etc.)
            if "subtype" in msg:
                continue
            # Skip empty messages
            text = msg.get("text", "").strip()
            if not text:
                continue

            messages.append(text)

        # Handle pagination
        if response.get("has_more"):
            cursor = response.get("response_metadata", {}).get("next_cursor")
        else:
            break

        if len(messages) >= limit:
            break

    return messages[:limit]
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_slack_fetcher.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/slack_fetcher.py tests/test_slack_fetcher.py
git commit -m "feat: add Slack message fetcher with pagination"
```

---

## Task 3: Ollama Filter Module

**Files:**
- Create: `slack-song-generator/src/filter.py`
- Create: `slack-song-generator/tests/test_filter.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_filter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.filter'`

**Step 3: Write minimal implementation**

```python
# src/filter.py
from dataclasses import dataclass

import requests


@dataclass
class FilterConfig:
    model: str = "llama3"
    base_url: str = "http://localhost:11434"


CLASSIFICATION_PROMPT = """Is this message a potential song title for a band?
Not discussion about titles - the title itself.
Reply only YES or NO.

Message: "{message}"
"""


def classify_message(message: str, config: FilterConfig) -> bool:
    """Ask Ollama if a message is a song title."""
    prompt = CLASSIFICATION_PROMPT.format(message=message)

    response = requests.post(
        f"{config.base_url}/api/generate",
        json={
            "model": config.model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    answer = response.json().get("response", "").strip().upper()
    return answer.startswith("YES")


def filter_song_titles(messages: list[str], config: FilterConfig) -> list[str]:
    """Filter a list of messages to only those classified as song titles."""
    return [msg for msg in messages if classify_message(msg, config)]
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_filter.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/filter.py tests/test_filter.py
git commit -m "feat: add Ollama-based song title filter"
```

---

## Task 4: Chaos Generator Module

**Files:**
- Create: `slack-song-generator/src/generator.py`
- Create: `slack-song-generator/tests/test_generator.py`

**Step 1: Write the failing test**

```python
# tests/test_generator.py
import pytest
import random

from src.generator import (
    generate_chaos_styles,
    GeneratorConfig,
    NEON_PALETTE,
    FONTS,
)


def test_generate_chaos_styles_deterministic_with_seed():
    """Same seed should produce same styles."""
    config = GeneratorConfig(seed=42)
    titles = ["Title A", "Title B", "Title C"]

    styles1 = generate_chaos_styles(titles, config)
    styles2 = generate_chaos_styles(titles, config)

    assert styles1 == styles2


def test_generate_chaos_styles_respects_max_rotation():
    """Rotation should not exceed max_rotation."""
    config = GeneratorConfig(seed=42, max_rotation=15)
    titles = ["Title"] * 50

    styles = generate_chaos_styles(titles, config)

    for style in styles:
        assert -15 <= style["rotation"] <= 15


def test_generate_chaos_styles_uses_palette():
    """Colors should come from specified palette."""
    config = GeneratorConfig(seed=42, color_palette="neon")
    titles = ["Title"] * 20

    styles = generate_chaos_styles(titles, config)

    for style in styles:
        assert style["color"] in NEON_PALETTE
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_generator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.generator'`

**Step 3: Write minimal implementation**

```python
# src/generator.py
from dataclasses import dataclass, field
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


NEON_PALETTE = ["#ff00ff", "#00ff00", "#00ffff", "#ffff00", "#ff0000", "#ff6600", "#ff0099"]
PASTEL_PALETTE = ["#ffb3ba", "#baffc9", "#bae1ff", "#ffffba", "#ffdfba"]
MONO_PALETTE = ["#000000", "#333333", "#666666", "#999999", "#cccccc"]

PALETTES = {
    "neon": NEON_PALETTE,
    "pastel": PASTEL_PALETTE,
    "mono": MONO_PALETTE,
}

FONTS = ["Comic Sans MS", "Courier New", "Arial", "Times New Roman", "Impact"]


@dataclass
class GeneratorConfig:
    seed: int | None = None
    max_rotation: int = 30
    color_palette: str = "neon"
    font_chaos: int = 5
    density: int = 5
    effects_enabled: list[str] = field(default_factory=lambda: ["shadows", "borders"])
    media_dir: Path | None = None


@dataclass
class TitleStyle:
    text: str
    left: float
    top: float
    rotation: int
    font_size: int
    color: str
    font_family: str
    text_shadow: str | None
    border: str | None
    z_index: int


def generate_chaos_styles(titles: list[str], config: GeneratorConfig) -> list[dict]:
    """Generate randomized styles for each title."""
    if config.seed is not None:
        random.seed(config.seed)

    palette = PALETTES.get(config.color_palette, NEON_PALETTE)
    available_fonts = FONTS[:config.font_chaos]

    styles = []
    for i, title in enumerate(titles):
        left = random.uniform(5, 85)
        top = random.uniform(5, 90)
        rotation = random.randint(-config.max_rotation, config.max_rotation)
        font_size = random.randint(12, 48)
        color = random.choice(palette)
        font_family = random.choice(available_fonts)

        text_shadow = None
        if "shadows" in config.effects_enabled and random.random() > 0.5:
            shadow_color = random.choice(palette)
            text_shadow = f"2px 2px 4px {shadow_color}"

        border = None
        if "borders" in config.effects_enabled and random.random() > 0.7:
            border_color = random.choice(palette)
            border = f"2px dotted {border_color}"

        styles.append({
            "text": title,
            "left": left,
            "top": top,
            "rotation": rotation,
            "font_size": font_size,
            "color": color,
            "font_family": font_family,
            "text_shadow": text_shadow,
            "border": border,
            "z_index": i,
        })

    return styles


def get_media_files(media_dir: Path | None) -> list[str]:
    """Get list of image/GIF files from media directory."""
    if media_dir is None or not media_dir.exists():
        return []

    extensions = {".gif", ".png", ".jpg", ".jpeg", ".webp"}
    return [f.name for f in media_dir.iterdir() if f.suffix.lower() in extensions]


def generate_html(
    titles: list[str],
    config: GeneratorConfig,
    output_path: Path,
    template_dir: Path | None = None,
) -> None:
    """Generate the chaotic HTML page."""
    if template_dir is None:
        template_dir = Path(__file__).parent / "templates"

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("chaos.html.j2")

    styles = generate_chaos_styles(titles, config)
    media_files = get_media_files(config.media_dir)

    # Generate random positions for media if present
    media_styles = []
    if media_files and config.seed is not None:
        random.seed(config.seed + 1000)  # Different seed for media
    for media_file in media_files:
        media_styles.append({
            "src": media_file,
            "left": random.uniform(0, 90),
            "top": random.uniform(0, 90),
            "rotation": random.randint(-20, 20),
            "width": random.randint(50, 200),
            "z_index": random.randint(0, len(titles)),
        })

    html = template.render(
        title_styles=styles,
        media_styles=media_styles,
        config=config,
    )

    output_path.write_text(html)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_generator.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/generator.py tests/test_generator.py
git commit -m "feat: add chaos HTML generator with randomized styles"
```

---

## Task 5: Jinja2 Template

**Files:**
- Create: `slack-song-generator/src/templates/chaos.html.j2`

**Step 1: Create the chaos template**

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SONG TITLE LIBRARY</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            min-height: 100vh;
            background: linear-gradient(45deg, #ffcccc, #ccffcc, #ccccff);
            overflow-x: hidden;
            position: relative;
        }

        .header {
            text-align: center;
            padding: 20px;
            font-family: 'Comic Sans MS', cursive;
            font-size: 2rem;
            color: #ff00ff;
            text-shadow: 3px 3px 0 #00ffff, -3px -3px 0 #ffff00;
            position: relative;
            z-index: 9999;
        }

        .title {
            position: absolute;
            white-space: nowrap;
            cursor: default;
            transition: transform 0.3s ease;
        }

        .title:hover {
            transform: scale(1.2);
            z-index: 10000 !important;
        }

        .media {
            position: absolute;
            pointer-events: none;
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        .blink {
            animation: blink 1s infinite;
        }
    </style>
</head>
<body>
    <div class="header">
        ★ SONG TITLE LIBRARY ★
    </div>

    {% for style in title_styles %}
    <div class="title{% if loop.index % 17 == 0 %} blink{% endif %}"
         style="
            left: {{ style.left }}%;
            top: {{ style.top }}%;
            transform: rotate({{ style.rotation }}deg);
            font-size: {{ style.font_size }}px;
            color: {{ style.color }};
            font-family: '{{ style.font_family }}', sans-serif;
            {% if style.text_shadow %}text-shadow: {{ style.text_shadow }};{% endif %}
            {% if style.border %}border: {{ style.border }}; padding: 5px;{% endif %}
            z-index: {{ style.z_index }};
         ">
        {{ style.text }}
    </div>
    {% endfor %}

    {% for media in media_styles %}
    <img class="media"
         src="{{ media.src }}"
         style="
            left: {{ media.left }}%;
            top: {{ media.top }}%;
            transform: rotate({{ media.rotation }}deg);
            width: {{ media.width }}px;
            z-index: {{ media.z_index }};
         "
         alt="">
    {% endfor %}
</body>
</html>
```

**Step 2: Commit**

```bash
git add src/templates/chaos.html.j2
git commit -m "feat: add chaos HTML Jinja2 template"
```

---

## Task 6: Cache Module

**Files:**
- Create: `slack-song-generator/src/cache.py`
- Create: `slack-song-generator/tests/test_cache.py`

**Step 1: Write the failing test**

```python
# tests/test_cache.py
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
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cache.py -v
```

Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/cache.py
import json
from pathlib import Path


def save_titles(titles: list[str], cache_path: Path) -> None:
    """Save filtered titles to JSON cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(titles, indent=2))


def load_titles(cache_path: Path) -> list[str]:
    """Load titles from JSON cache. Returns empty list if not found."""
    if not cache_path.exists():
        return []
    return json.loads(cache_path.read_text())
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cache.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/cache.py tests/test_cache.py
git commit -m "feat: add JSON cache for filtered titles"
```

---

## Task 7: CLI Entrypoint

**Files:**
- Create: `slack-song-generator/src/cli.py`

**Step 1: Create the CLI module**

```python
# src/cli.py
import argparse
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
import os

from src.slack_fetcher import fetch_messages, SlackConfig
from src.filter import filter_song_titles, FilterConfig
from src.generator import generate_html, GeneratorConfig
from src.cache import save_titles, load_titles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate chaotic geocities-style pages from Slack song titles"
    )

    parser.add_argument(
        "--channel-id",
        help="Slack channel ID (overrides .env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("songtitles.html"),
        help="Output HTML file path",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible chaos",
    )
    parser.add_argument(
        "--media-dir",
        type=Path,
        help="Directory of images/GIFs to scatter",
    )
    parser.add_argument(
        "--density",
        type=int,
        choices=range(1, 11),
        default=5,
        help="How packed/sparse (1-10)",
    )
    parser.add_argument(
        "--color-palette",
        choices=["neon", "pastel", "mono", "random"],
        default="neon",
        help="Color palette preset",
    )
    parser.add_argument(
        "--font-chaos",
        type=int,
        choices=range(1, 6),
        default=5,
        help="How many different fonts (1-5)",
    )
    parser.add_argument(
        "--max-rotation",
        type=int,
        default=30,
        help="Maximum rotation in degrees",
    )
    parser.add_argument(
        "--title-limit",
        type=int,
        default=500,
        help="Maximum titles to display",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Fetch & filter only, don't generate HTML",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Skip fetch, use cached titles",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Randomize all visual settings",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=Path("cache/titles.json"),
        help="Path to titles cache file",
    )

    return parser.parse_args()


def randomize_config(seed: int | None) -> dict:
    """Generate random config values."""
    if seed is not None:
        random.seed(seed)
    return {
        "color_palette": random.choice(["neon", "pastel", "mono"]),
        "font_chaos": random.randint(1, 5),
        "max_rotation": random.randint(10, 45),
        "density": random.randint(1, 10),
    }


def main() -> int:
    load_dotenv()
    args = parse_args()

    # Get Slack config from env or args
    token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = args.channel_id or os.getenv("SLACK_CHANNEL_ID")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")

    cache_path = args.cache_file

    # Fetch and filter (unless --generate-only)
    if not args.generate_only:
        if not token:
            print("Error: SLACK_BOT_TOKEN not set in .env", file=sys.stderr)
            return 1
        if not channel_id:
            print("Error: SLACK_CHANNEL_ID not set (use --channel-id or .env)", file=sys.stderr)
            return 1

        print(f"Fetching messages from Slack channel {channel_id}...")
        slack_config = SlackConfig(token=token, channel_id=channel_id)
        messages = fetch_messages(slack_config, limit=args.title_limit)
        print(f"Fetched {len(messages)} messages")

        print("Filtering for song titles with Ollama...")
        filter_config = FilterConfig(model=ollama_model)
        try:
            titles = filter_song_titles(messages, filter_config)
        except Exception as e:
            print(f"Error connecting to Ollama: {e}", file=sys.stderr)
            print("Make sure Ollama is running: ollama serve", file=sys.stderr)
            return 1

        print(f"Found {len(titles)} song titles")

        save_titles(titles, cache_path)
        print(f"Saved to cache: {cache_path}")

        if args.fetch_only:
            return 0
    else:
        titles = load_titles(cache_path)
        if not titles:
            print(f"Error: No cached titles found at {cache_path}", file=sys.stderr)
            print("Run without --generate-only first to fetch titles", file=sys.stderr)
            return 1
        print(f"Loaded {len(titles)} titles from cache")

    # Apply --random if set
    if args.random:
        random_settings = randomize_config(args.seed)
        args.color_palette = random_settings["color_palette"]
        args.font_chaos = random_settings["font_chaos"]
        args.max_rotation = random_settings["max_rotation"]
        args.density = random_settings["density"]
        print(f"Randomized settings: {random_settings}")

    # Generate HTML
    gen_config = GeneratorConfig(
        seed=args.seed,
        max_rotation=args.max_rotation,
        color_palette=args.color_palette,
        font_chaos=args.font_chaos,
        density=args.density,
        media_dir=args.media_dir,
    )

    print(f"Generating chaotic HTML...")
    generate_html(titles, gen_config, args.output)
    print(f"Generated: {args.output}")

    if args.seed:
        print(f"Seed: {args.seed} (use this to reproduce)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Create generate-song-page.py wrapper script**

```python
#!/usr/bin/env python3
# generate-song-page.py
from src.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
```

**Step 3: Make wrapper executable and commit**

```bash
chmod +x generate-song-page.py
git add src/cli.py generate-song-page.py
git commit -m "feat: add CLI entrypoint with all options"
```

---

## Task 8: README with Slack Setup Guide

**Files:**
- Create: `slack-song-generator/README.md`

**Step 1: Create comprehensive README**

```markdown
# Slack Song Title Generator

Generate chaotic geocities-style HTML pages from song titles in your Slack channel.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [Ollama](https://ollama.ai/) running locally with a model (llama3 recommended)
- A Slack workspace where you can create apps

## Installation

```bash
cd slack-song-generator
uv sync
```

## Slack App Setup (One-Time)

### 1. Create the App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name it something like "Song Title Fetcher"
4. Select your workspace
5. Click **Create App**

### 2. Add Permissions

1. In the left sidebar, click **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Click **Add an OAuth Scope** and add:
   - `channels:history` (read messages from public channels)
   - `channels:read` (list channels)

### 3. Install to Workspace

1. Scroll up and click **Install to Workspace**
2. Review permissions and click **Allow**
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 4. Invite Bot to Channel

1. In Slack, go to your song titles channel
2. Type `/invite @YourBotName` (use the name you gave your app)

### 5. Get Channel ID

1. Right-click on the channel name
2. Click **View channel details**
3. At the bottom, copy the **Channel ID** (starts with `C`)

### 6. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values:
# SLACK_BOT_TOKEN=xoxb-your-token-here
# SLACK_CHANNEL_ID=C0XXXXXXX
```

## Ollama Setup

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama
ollama serve

# Pull a model (in another terminal)
ollama pull llama3
```

## Usage

```bash
# Basic generation
./generate-song-page.py --output ../songtitles.html

# Pure chaos mode (randomize all settings)
./generate-song-page.py --random --output ../songtitles.html

# Reproducible chaos (same seed = same layout)
./generate-song-page.py --random --seed 42 --output ../songtitles.html

# With scattered images
./generate-song-page.py --media-dir ./gifs --output ../songtitles.html

# Just fetch and cache titles (no HTML generation)
./generate-song-page.py --fetch-only

# Regenerate from cache (skip Slack API call)
./generate-song-page.py --generate-only --random
```

## All Options

| Option | Description | Default |
|--------|-------------|---------|
| `--channel-id` | Slack channel ID (overrides .env) | from .env |
| `--output` | Output HTML file path | songtitles.html |
| `--seed` | Random seed for reproducible chaos | random |
| `--media-dir` | Directory of images/GIFs to scatter | none |
| `--density` | How packed/sparse (1-10) | 5 |
| `--color-palette` | neon, pastel, mono, or random | neon |
| `--font-chaos` | How many fonts to use (1-5) | 5 |
| `--max-rotation` | Max rotation degrees | 30 |
| `--title-limit` | Max titles to fetch | 500 |
| `--fetch-only` | Only fetch/filter, no HTML | false |
| `--generate-only` | Use cache, skip Slack | false |
| `--random` | Randomize all visual settings | false |

## Troubleshooting

**"Error connecting to Ollama"**
- Make sure Ollama is running: `ollama serve`
- Check if model is pulled: `ollama list`

**"SLACK_BOT_TOKEN not set"**
- Copy `.env.example` to `.env` and fill in your token

**"channel_not_found" error**
- Make sure the bot is invited to the channel
- Verify the channel ID is correct

**No titles found after filtering**
- The channel might have mostly discussion, not titles
- Try with `--fetch-only` to see raw messages in cache
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with Slack setup guide"
```

---

## Task 9: Integration Test

**Files:**
- Create: `slack-song-generator/tests/test_integration.py`

**Step 1: Write integration test with mocks**

```python
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
```

**Step 2: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full pipeline"
```

---

## Task 10: Final Verification

**Step 1: Run full test suite**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 2: Verify CLI help works**

```bash
./generate-song-page.py --help
```

Expected: Shows all options

**Step 3: Final commit if any cleanup needed**

```bash
git status
# If clean, nothing to commit
# If any loose files, add and commit
```

**Step 4: Summary**

The slack-song-generator is complete with:
- Slack message fetching with pagination
- Ollama-based song title filtering
- Chaotic HTML generation with full randomization options
- JSON caching for quick regeneration
- Comprehensive CLI with all options
- Full test coverage
- Detailed README with Slack setup walkthrough

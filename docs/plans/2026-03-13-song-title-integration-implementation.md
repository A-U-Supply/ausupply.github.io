# Song Title Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate song titles from #song-titles Slack channel as creative seeds for the midi-bot and glottisdale-bot, with a new scraper bot and automated HTML page generation.

**Architecture:** A new `song-titles-bot/` scrapes and filters Slack messages into `titles.json`. The midi-bot and glottisdale-bot each independently pick random unused titles from this JSON. The midi-bot uses the title as the primary LLM prompt seed (replacing headlines). The glottisdale-bot hashes the title into a deterministic `--seed` and uses it as a label. The hymnal-bot gets the title transitively from the Daily MIDI message.

**Tech Stack:** Python 3.11, slack-sdk, huggingface-hub, Jinja2, GitHub Actions

**Spec:** `docs/plans/2026-03-13-song-title-integration-design.md`

---

## Chunk 1: Data Migration + Song Titles Bot

### Task 1: Migrate existing titles to new schema

**Files:**
- Read: `slack-song-generator/cache/titles.json`
- Create: `song-titles-bot/titles.json`

- [ ] **Step 1: Write migration script**

Create a one-time migration script. No need to commit it — just run it to produce the output.

```python
#!/usr/bin/env python3
"""Migrate titles from flat array to new schema with synthetic IDs."""
import json
from pathlib import Path

src = Path("slack-song-generator/cache/titles.json")
old = json.loads(src.read_text())

new = []
for i, title in enumerate(old):
    new.append({
        "id": f"legacy-{i:04d}",
        "title": title.strip(),
        "date": None,
        "author_id": None,
        "permalink": None,
    })

dst = Path("song-titles-bot/titles.json")
dst.parent.mkdir(exist_ok=True)
dst.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
print(f"Migrated {len(new)} titles")
```

- [ ] **Step 2: Run migration, verify output**

Run: `mkdir -p song-titles-bot && python migrate_titles.py`

Verify: `python -c "import json; d=json.loads(open('song-titles-bot/titles.json').read()); print(len(d)); print(d[0]); print(d[-1])"`

Expected: 139 titles, each with `id`, `title`, `date`, `author_id`, `permalink` fields.

- [ ] **Step 3: Commit**

```bash
git add song-titles-bot/titles.json
git commit -m "feat(song-titles-bot): migrate 139 existing titles to new schema

Migrates flat title array from slack-song-generator/cache/titles.json
to structured format with id, title, date, author_id, permalink fields.
Legacy titles get synthetic IDs (legacy-0000 through legacy-0138) and
null metadata since original Slack context wasn't preserved."
```

---

### Task 2: Song titles bot — Slack scraper

**Files:**
- Create: `song-titles-bot/src/__init__.py` (empty)
- Create: `song-titles-bot/src/slack_scraper.py`
- Create: `song-titles-bot/tests/__init__.py` (empty)
- Create: `song-titles-bot/tests/test_slack_scraper.py`

This module fetches messages from #song-titles. It follows the pattern in `slack-song-generator/src/slack_fetcher.py` but adds metadata extraction (date, author_id, permalink) and incremental fetching (only messages newer than the latest known ID).

- [ ] **Step 1: Write the failing test**

```python
# song-titles-bot/tests/test_slack_scraper.py
"""Tests for Slack scraper — uses a fake WebClient."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.slack_scraper import fetch_new_messages


def _make_msg(ts: str, text: str, user: str = "U123", bot_id: str = None, subtype: str = None):
    """Helper to build a Slack message dict."""
    msg = {"ts": ts, "text": text, "user": user}
    if bot_id:
        msg["bot_id"] = bot_id
    if subtype:
        msg["subtype"] = subtype
    return msg


def test_fetch_new_messages_basic():
    """Fetches human messages, skips bots and system messages."""
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
    assert results[0]["author_id"] == "U111"
    assert results[1]["title"] == "first title"


def test_fetch_new_messages_incremental():
    """Only returns messages newer than after_ts."""
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


def test_fetch_new_messages_skips_empty_and_threads():
    """Skips empty messages and thread replies."""
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
            _make_msg("1710000000.000000", "   "),
        ],
        "has_more": False,
    }

    results = fetch_new_messages(client, channel_name="song-titles", after_ts=None)

    assert len(results) == 1
    assert results[0]["title"] == "good title"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd song-titles-bot && python -m pytest tests/test_slack_scraper.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.slack_scraper'`

- [ ] **Step 3: Write implementation**

```python
# song-titles-bot/src/slack_scraper.py
"""Fetch song title messages from Slack #song-titles channel."""
import logging
from datetime import datetime, timezone

from slack_sdk import WebClient

logger = logging.getLogger(__name__)


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Find a Slack channel ID by name."""
    cursor = None
    while True:
        kwargs = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == channel_name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


def fetch_new_messages(
    client: WebClient,
    channel_name: str,
    after_ts: str | None = None,
) -> list[dict]:
    """Fetch human messages from #song-titles, optionally only those newer than after_ts.

    Returns list of dicts with keys: id, title, date, author_id, permalink.
    Messages are returned newest-first.
    """
    channel_id = find_channel_id(client, channel_name)
    if not channel_id:
        logger.error(f"Channel #{channel_name} not found")
        return []

    messages = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        if after_ts:
            kwargs["oldest"] = after_ts

        resp = client.conversations_history(**kwargs)

        for msg in resp.get("messages", []):
            # Skip bots, system messages, thread replies
            if "bot_id" in msg or "subtype" in msg:
                continue
            if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]:
                continue

            text = msg.get("text", "").strip()
            if not text:
                continue

            # Skip messages at or before the cutoff
            if after_ts and float(msg["ts"]) <= float(after_ts):
                continue

            ts = msg["ts"]
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)

            messages.append({
                "id": ts,
                "title": text,
                "date": dt.strftime("%Y-%m-%d"),
                "author_id": msg.get("user"),
                "permalink": f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
            })

        if resp.get("has_more"):
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        else:
            break

    logger.info(f"Fetched {len(messages)} new messages from #{channel_name}")
    return messages
```

Also create the `__init__.py` files:

```bash
touch song-titles-bot/src/__init__.py song-titles-bot/tests/__init__.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd song-titles-bot && python -m pytest tests/test_slack_scraper.py -v`

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add song-titles-bot/src/ song-titles-bot/tests/
git commit -m "feat(song-titles-bot): add Slack scraper module

Fetches messages from #song-titles with cursor-based pagination.
Skips bots, system messages, thread replies, and empty messages.
Supports incremental fetching via after_ts parameter.
Returns structured dicts with id, title, date, author_id, permalink."
```

---

### Task 3: Song titles bot — HF Inference filter

**Files:**
- Create: `song-titles-bot/src/filter.py`
- Create: `song-titles-bot/tests/test_filter.py`

Replaces the old Ollama-based filter with HF Inference API (Llama-3.3-70B-Instruct).

- [ ] **Step 1: Write the failing test**

```python
# song-titles-bot/tests/test_filter.py
"""Tests for HF Inference song title filter."""
from unittest.mock import MagicMock, patch

from src.filter import classify_messages, CLASSIFICATION_PROMPT


def _make_completion(content: str):
    """Build a fake HF chat_completion response."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_classify_messages_filters_correctly():
    """YES responses kept, NO responses dropped."""
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
    assert client.chat_completion.call_count == 3


def test_classify_messages_handles_whitespace_and_case():
    """Handles responses like ' yes ', 'Yes.', etc."""
    client = MagicMock()
    client.chat_completion.side_effect = [
        _make_completion("  Yes.  "),
        _make_completion("  no  "),
    ]

    messages = [
        {"id": "1", "title": "good title"},
        {"id": "2", "title": "bad msg"},
    ]

    result = classify_messages(messages, client, model="test-model")

    assert len(result) == 1
    assert result[0]["title"] == "good title"


def test_classify_messages_empty_input():
    """Returns empty list for empty input."""
    client = MagicMock()

    result = classify_messages([], client, model="test-model")

    assert result == []
    assert client.chat_completion.call_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd song-titles-bot && python -m pytest tests/test_filter.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# song-titles-bot/src/filter.py
"""Filter Slack messages to identify song titles using HF Inference API."""
import logging

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = (
    'Is this Slack message a potential song title? Not discussion about titles — the title itself.\n'
    'Reply only YES or NO.\n\n'
    'Message: "{message}"'
)


def classify_messages(
    messages: list[dict],
    client: InferenceClient,
    model: str,
) -> list[dict]:
    """Filter message dicts to only those classified as song titles.

    Each message dict must have a 'title' key with the text to classify.
    Returns the subset of messages that the LLM considers song titles.
    """
    if not messages:
        return []

    results = []
    for msg in messages:
        prompt = CLASSIFICATION_PROMPT.format(message=msg["title"])
        try:
            resp = client.chat_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            answer = resp.choices[0].message.content.strip().upper()
            if answer.startswith("YES"):
                results.append(msg)
                logger.debug(f"YES: {msg['title'][:50]}")
            else:
                logger.debug(f"NO:  {msg['title'][:50]}")
        except Exception as e:
            logger.warning(f"Classification failed for '{msg['title'][:50]}': {e}, keeping message")
            results.append(msg)

    logger.info(f"Classified {len(messages)} messages: {len(results)} are song titles")
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd song-titles-bot && python -m pytest tests/test_filter.py -v`

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add song-titles-bot/src/filter.py song-titles-bot/tests/test_filter.py
git commit -m "feat(song-titles-bot): add HF Inference API song title filter

Classifies Slack messages as song titles vs conversation using
Llama-3.3-70B-Instruct via Hugging Face Inference API. Replaces
the old Ollama-based filter from slack-song-generator."
```

---

### Task 4: Song titles bot — HTML generator

**Files:**
- Create: `song-titles-bot/src/html_generator.py`
- Create: `song-titles-bot/templates/junkyard.html.j2`
- Create: `song-titles-bot/tests/test_html_generator.py`
- Reference: `this-song-is-a-junkyard.html` (for the full interactive JS/CSS to replicate in template)

The Jinja2 template must reproduce the full interactivity from the current page: draggable divs with random positioning/rotation/size/color, toolbar controls, localStorage persistence, touch support. The generator module renders the template from `titles.json`.

- [ ] **Step 1: Write the failing test**

```python
# song-titles-bot/tests/test_html_generator.py
"""Tests for HTML generator."""
from pathlib import Path

from src.html_generator import generate_html


def test_generate_html_contains_titles():
    """Generated HTML includes all song titles."""
    titles = [
        {"id": "1", "title": "Tip of the Fatberg", "date": "2026-01-15", "author_id": "U1", "permalink": None},
        {"id": "2", "title": "sleep cartel", "date": "2026-01-16", "author_id": "U2", "permalink": None},
    ]

    html = generate_html(titles)

    assert "Tip of the Fatberg" in html
    assert "sleep cartel" in html
    assert "<!DOCTYPE html>" in html


def test_generate_html_has_interactivity():
    """Generated HTML has draggable/toolbar/localStorage JS."""
    titles = [{"id": "1", "title": "test", "date": None, "author_id": None, "permalink": None}]

    html = generate_html(titles)

    assert "localStorage" in html
    assert "class=\"title\"" in html or 'class="title"' in html
    assert "toolbar" in html.lower()
    assert "touchstart" in html or "touch-action" in html


def test_generate_html_uses_shared_header():
    """Generated HTML has shared header with cheeze-bourger2.png."""
    titles = [{"id": "1", "title": "test", "date": None, "author_id": None, "permalink": None}]

    html = generate_html(titles)

    assert "cheeze-bourger2.png" in html
    assert "vcfmw.css" in html


def test_generate_html_empty_titles():
    """Generates valid HTML even with no titles."""
    html = generate_html([])

    assert "<!DOCTYPE html>" in html
    assert "SONG TITLE LIBRARY" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd song-titles-bot && python -m pytest tests/test_html_generator.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the Jinja2 template**

Copy the full CSS, JS, and HTML structure from `this-song-is-a-junkyard.html` into `song-titles-bot/templates/junkyard.html.j2`. The key change: replace the ~140 hardcoded `<div class="title" ...>` elements with a Jinja2 loop:

```jinja2
{% for t in titles %}
<div class="title" data-id="{{ t.id }}" style="left: {{ t.left }}%; top: {{ t.top }}px; font-size: {{ t.font_size }}px; color: {{ t.color }}; transform: rotate({{ t.rotation }}deg); z-index: {{ t.z_index }};">{{ t.title }}</div>
{% endfor %}
```

The random positioning/color/size values are computed by the Python generator, not in the template. The template is otherwise a direct copy of the existing page's HTML structure (CSS animations, toolbar, drag/touch/localStorage JS).

- [ ] **Step 4: Write implementation**

```python
# song-titles-bot/src/html_generator.py
"""Generate the interactive this-song-is-a-junkyard.html page from titles.json."""
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

COLORS = [
    "#ff0000", "#ff4400", "#ff8800", "#ffcc00", "#ffff00",
    "#88ff00", "#00ff00", "#00ff88", "#00ffff", "#0088ff",
    "#0000ff", "#4400ff", "#8800ff", "#ff00ff", "#ff0088",
    "#ffffff", "#ff6666", "#66ff66", "#6666ff", "#ffff66",
]

FONTS = [
    "'Comic Sans MS', cursive",
    "'Impact', sans-serif",
    "'Courier New', monospace",
    "'Arial Black', sans-serif",
    "'Georgia', serif",
    "'Trebuchet MS', sans-serif",
    "'Verdana', sans-serif",
    "'Papyrus', fantasy",
]


def _randomize_title(title: dict, index: int) -> dict:
    """Add random visual properties to a title for initial layout."""
    return {
        **title,
        "left": random.uniform(2, 85),
        "top": 120 + random.randint(0, 2400),
        "font_size": random.randint(14, 42),
        "color": random.choice(COLORS),
        "rotation": random.randint(-30, 30),
        "font_family": random.choice(FONTS),
        "z_index": index + 1,
    }


def generate_html(titles: list[dict]) -> str:
    """Render the song titles page from a list of title dicts."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("junkyard.html.j2")

    styled_titles = [_randomize_title(t, i) for i, t in enumerate(titles)]

    return template.render(titles=styled_titles)
```

- [ ] **Step 5: Create the Jinja2 template file**

Create `song-titles-bot/templates/junkyard.html.j2`. This file should be a direct adaptation of the current `this-song-is-a-junkyard.html`:
- Copy all CSS (inline `<style>` block with animations, toolbar styles, etc.)
- Copy all JS (drag/touch handling, localStorage save/load, toolbar controls, keyboard shortcuts)
- Replace hardcoded `<div class="title">` elements with the Jinja2 `{% for %}` loop above
- Keep the shared header (`vcfmw.css` link, cheeze-bourger2.png image, h1)
- Use relative paths for all assets (`vcfmw.css`, `img/cheeze-bourger2.png`, `index.html`)

The template is large (~300 lines of CSS + JS) but is a mechanical copy from the existing page. The only dynamic part is the title divs.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd song-titles-bot && python -m pytest tests/test_html_generator.py -v`

Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add song-titles-bot/src/html_generator.py song-titles-bot/templates/junkyard.html.j2 song-titles-bot/tests/test_html_generator.py
git commit -m "feat(song-titles-bot): add HTML generator with Jinja2 template

Generates the interactive this-song-is-a-junkyard.html page from
titles.json data. Reproduces full interactivity: draggable divs,
pinch/rotate touch support, localStorage persistence, toolbar
controls, keyboard shortcuts. Random positioning/color/size computed
in Python, template handles layout."
```

---

### Task 5: Song titles bot — Config + orchestrator

**Files:**
- Create: `song-titles-bot/config.yaml`
- Create: `song-titles-bot/src/config.py`
- Create: `song-titles-bot/bot.py`
- Create: `song-titles-bot/requirements.txt`
- Create: `song-titles-bot/tests/test_bot.py`

- [ ] **Step 1: Write the failing test**

```python
# song-titles-bot/tests/test_bot.py
"""Integration test for the bot orchestrator."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot import run_bot


def test_run_bot_dry_run(tmp_path):
    """Dry run: scrapes, filters, saves titles, generates HTML."""
    # Seed titles.json with one existing title
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([
        {"id": "legacy-0000", "title": "old title", "date": None, "author_id": None, "permalink": None}
    ]))

    html_path = tmp_path / "output.html"

    with patch("bot.WebClient") as mock_client_cls, \
         patch("bot.InferenceClient") as mock_hf_cls:

        # Mock Slack scraper
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.conversations_list.return_value = {
            "channels": [{"name": "song-titles", "id": "C999"}],
            "response_metadata": {"next_cursor": ""},
        }
        mock_client.conversations_history.return_value = {
            "messages": [
                {"ts": "1710000001.000001", "text": "new song title", "user": "U555"},
            ],
            "has_more": False,
        }

        # Mock HF filter (says YES)
        mock_hf = MagicMock()
        mock_hf_cls.return_value = mock_hf
        choice = MagicMock()
        choice.message.content = "YES"
        resp = MagicMock()
        resp.choices = [choice]
        mock_hf.chat_completion.return_value = resp

        result = run_bot(
            titles_path=titles_path,
            html_output_path=html_path,
            channel_name="song-titles",
            hf_token="fake",
            slack_token="fake",
            model="test-model",
        )

    assert result == 0

    # Verify titles.json was updated
    titles = json.loads(titles_path.read_text())
    assert len(titles) == 2
    assert titles[1]["title"] == "new song title"
    assert titles[1]["id"] == "1710000001.000001"

    # Verify HTML was generated
    assert html_path.exists()
    html = html_path.read_text()
    assert "old title" in html
    assert "new song title" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd song-titles-bot && python -m pytest tests/test_bot.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write config**

```yaml
# song-titles-bot/config.yaml
channel: song-titles
model: meta-llama/Llama-3.3-70B-Instruct
titles_path: titles.json
html_output_path: ../this-song-is-a-junkyard.html
```

```python
# song-titles-bot/src/config.py
"""Configuration loader."""
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "channel": "song-titles",
    "model": "meta-llama/Llama-3.3-70B-Instruct",
    "titles_path": "titles.json",
    "html_output_path": "../this-song-is-a-junkyard.html",
}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load config from YAML, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config.update(file_config)
    return config
```

- [ ] **Step 4: Write orchestrator**

```python
#!/usr/bin/env python3
# song-titles-bot/bot.py
"""Song Titles Bot — scrape, filter, save, generate HTML."""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from huggingface_hub import InferenceClient
from slack_sdk import WebClient

from src.slack_scraper import fetch_new_messages
from src.filter import classify_messages
from src.html_generator import generate_html
from src.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_bot(
    titles_path: Path,
    html_output_path: Path,
    channel_name: str,
    hf_token: str,
    slack_token: str,
    model: str,
) -> int:
    """Main bot logic. Returns exit code."""
    # Load existing titles
    if titles_path.exists():
        existing = json.loads(titles_path.read_text())
    else:
        existing = []
    logger.info(f"Loaded {len(existing)} existing titles")

    # Find latest known timestamp for incremental fetching
    known_ids = {t["id"] for t in existing}
    latest_ts = None
    for t in existing:
        if t["id"] and not t["id"].startswith("legacy-"):
            if latest_ts is None or float(t["id"]) > float(latest_ts):
                latest_ts = t["id"]

    # Scrape new messages from Slack
    client = WebClient(token=slack_token)
    new_messages = fetch_new_messages(client, channel_name=channel_name, after_ts=latest_ts)
    logger.info(f"Fetched {len(new_messages)} new messages")

    # Filter for song titles
    if new_messages:
        hf_client = InferenceClient(token=hf_token)
        filtered = classify_messages(new_messages, hf_client, model=model)
        logger.info(f"Filtered to {len(filtered)} song titles")

        # Deduplicate and append
        added = 0
        for msg in filtered:
            if msg["id"] not in known_ids:
                existing.append(msg)
                known_ids.add(msg["id"])
                added += 1
        logger.info(f"Added {added} new titles (total: {len(existing)})")
    else:
        logger.info("No new messages to process")

    # Save updated titles
    titles_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n")

    # Generate HTML
    html = generate_html(existing)
    html_output_path.write_text(html)
    logger.info(f"Generated HTML at {html_output_path} with {len(existing)} titles")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Song Titles Bot")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Skip Slack, just regenerate HTML")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    config = load_config(script_dir / args.config)

    hf_token = os.environ.get("HF_TOKEN", "")
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")

    if not slack_token and not args.dry_run:
        logger.error("SLACK_BOT_TOKEN required")
        return 1
    if not hf_token and not args.dry_run:
        logger.error("HF_TOKEN required")
        return 1

    titles_path = script_dir / config["titles_path"]
    html_output_path = script_dir / config["html_output_path"]

    if args.dry_run:
        # Just regenerate HTML from existing titles
        existing = json.loads(titles_path.read_text()) if titles_path.exists() else []
        html = generate_html(existing)
        html_output_path.write_text(html)
        logger.info(f"Dry run: regenerated HTML with {len(existing)} titles")
        return 0

    return run_bot(
        titles_path=titles_path,
        html_output_path=html_output_path,
        channel_name=config["channel"],
        hf_token=hf_token,
        slack_token=slack_token,
        model=config["model"],
    )


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Create requirements.txt**

```
slack-sdk>=3.21.0
huggingface-hub>=0.20.0
Jinja2>=3.1.0
PyYAML>=6.0
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd song-titles-bot && pip install -r requirements.txt && python -m pytest tests/test_bot.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add song-titles-bot/bot.py song-titles-bot/src/config.py song-titles-bot/config.yaml song-titles-bot/requirements.txt song-titles-bot/tests/test_bot.py
git commit -m "feat(song-titles-bot): add config and orchestrator

Bot orchestrates: scrape → filter → save → generate HTML.
Supports incremental fetching (only new messages since last run).
Dry-run mode regenerates HTML from existing titles.json."
```

---

## Chunk 2: midi-bot Changes

### Task 6: midi-bot — Title selector with usage tracking

**Files:**
- Create: `midi-bot/src/title_selector.py`
- Create: `midi-bot/tests/test_title_selector.py`

This module picks a random unused title from titles.json and tracks usage. The same logic will be duplicated (not shared) in glottisdale-bot.

- [ ] **Step 1: Write the failing test**

```python
# midi-bot/tests/test_title_selector.py
"""Tests for song title selection with usage tracking."""
import json
from pathlib import Path

from src.title_selector import select_title, load_titles


def test_load_titles(tmp_path):
    """Loads titles from JSON file."""
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([
        {"id": "1", "title": "first"},
        {"id": "2", "title": "second"},
    ]))

    titles = load_titles(titles_path)
    assert len(titles) == 2
    assert titles[0]["title"] == "first"


def test_select_title_picks_unused(tmp_path):
    """Picks from unused titles, records usage."""
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([
        {"id": "1", "title": "first"},
        {"id": "2", "title": "second"},
        {"id": "3", "title": "third"},
    ]))
    used_path = tmp_path / "used.json"
    used_path.write_text(json.dumps({"used_ids": ["1"]}))

    title = select_title(titles_path, used_path)

    assert title["id"] in ("2", "3")

    used = json.loads(used_path.read_text())
    assert title["id"] in used["used_ids"]
    assert "1" in used["used_ids"]


def test_select_title_resets_when_exhausted(tmp_path):
    """Resets used list when all titles have been used."""
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([
        {"id": "1", "title": "only one"},
    ]))
    used_path = tmp_path / "used.json"
    used_path.write_text(json.dumps({"used_ids": ["1"]}))

    title = select_title(titles_path, used_path)

    assert title["title"] == "only one"
    used = json.loads(used_path.read_text())
    assert used["used_ids"] == ["1"]


def test_select_title_creates_used_file(tmp_path):
    """Creates used-song-titles.json if it doesn't exist."""
    titles_path = tmp_path / "titles.json"
    titles_path.write_text(json.dumps([
        {"id": "1", "title": "first"},
    ]))
    used_path = tmp_path / "used.json"

    title = select_title(titles_path, used_path)

    assert title["title"] == "first"
    assert used_path.exists()


def test_load_titles_missing_file(tmp_path):
    """Returns empty list for missing titles file."""
    titles = load_titles(tmp_path / "nonexistent.json")
    assert titles == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd midi-bot && python -m pytest tests/test_title_selector.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# midi-bot/src/title_selector.py
"""Select random unused song titles with usage tracking."""
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


def load_titles(titles_path: Path) -> list[dict]:
    """Load titles from JSON file. Returns empty list if missing."""
    if not titles_path.exists():
        logger.warning(f"Titles file not found: {titles_path}")
        return []
    return json.loads(titles_path.read_text())


def select_title(titles_path: Path, used_path: Path) -> dict | None:
    """Pick a random unused title, record usage, return title dict.

    When all titles have been used, resets the used list and picks fresh.
    Returns None if titles file is empty or missing.
    """
    titles = load_titles(titles_path)
    if not titles:
        return None

    # Load used IDs
    if used_path.exists():
        used_data = json.loads(used_path.read_text())
    else:
        used_data = {"used_ids": []}

    used_ids = set(used_data["used_ids"])
    all_ids = {t["id"] for t in titles}

    # Find unused titles
    unused = [t for t in titles if t["id"] not in used_ids]

    if not unused:
        # All used — reset and pick from full pool
        logger.info(f"All {len(titles)} titles used, resetting pool")
        used_ids = set()
        unused = titles

    # Pick random
    title = random.choice(unused)
    used_ids.add(title["id"])

    # Save updated usage
    used_data["used_ids"] = sorted(used_ids & all_ids)  # prune stale IDs
    used_path.write_text(json.dumps(used_data, indent=2) + "\n")

    logger.info(f"Selected title: \"{title['title']}\" ({len(used_data['used_ids'])}/{len(titles)} used)")
    return title
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd midi-bot && python -m pytest tests/test_title_selector.py -v`

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add midi-bot/src/title_selector.py midi-bot/tests/test_title_selector.py
git commit -m "feat(midi-bot): add song title selector with usage tracking

Picks random unused titles from titles.json, tracks usage in
used-song-titles.json. Resets when pool exhausted. Returns None
if titles file missing (for graceful fallback to headlines)."
```

---

### Task 7: midi-bot — New prompt template + generator refactor

**Files:**
- Create: `midi-bot/prompt_template_song_title.txt`
- Modify: `midi-bot/src/generator.py:73-97` (add `build_llm_prompt_from_title`)
- Modify: `midi-bot/src/generator.py:176-213` (refactor `generate_music_params` signature)
- Modify: `midi-bot/prompt_template.txt:1,11` (remove "surrealist")
- Create: `midi-bot/tests/test_generator_title.py`

- [ ] **Step 1: Create the new prompt template**

```
# midi-bot/prompt_template_song_title.txt
You are a composer with severe internet brain rot. You select unusual musical parameters inspired by a song title and strange imagery.
---
The song title below is your primary creative seed. Let it drive your choices — the mood, tempo, scale, and instruments should all feel like they belong to a song with this name.

SONG TITLE:
"{title}"

Musical inspiration for today:
{inspirations}

TODAY'S SCALE OPTIONS (pick ONE — use the exact name):
{scales}

MELODY INSTRUMENTS:
{melody_instruments}

CHORD INSTRUMENTS:
{chord_instruments}

Output a JSON object with these exact keys:
- "scale": You MUST choose one of the numbered scales above. Copy the name EXACTLY. Do NOT use any scale not on this list.
- "root": a root note (e.g. "C", "F#", "Bb") — vary this, don't always pick C or A
- "chords": an array of exactly 4 chord symbols that work with the chosen scale (e.g. ["Am", "Dm7", "G7", "Cmaj7"])
- "tempo": a number between 40 and 200 (let the song title guide the energy)
- "temperature": a number between 0.5 and 1.5 (how wild the AI-generated melody and drums should be)
- "melody_instrument": a MIDI program number from the MELODY INSTRUMENTS list above
- "chord_instrument": a MIDI program number from the CHORD INSTRUMENTS list above
- "description": a single weird sentence inspired by the song title (with 1-3 emojis, Slack formatting allowed)

Output ONLY the JSON. No explanation. No markdown code fence. Just the raw JSON object.
```

- [ ] **Step 2: Write the failing test for the new prompt builder**

```python
# midi-bot/tests/test_generator_title.py
"""Tests for song-title-based prompt generation."""
from pathlib import Path

from src.generator import build_llm_prompt_from_title


def test_build_llm_prompt_from_title_basic():
    """Builds a prompt with the song title injected."""
    template = 'SONG TITLE:\n"{title}"\n\nInspirations:\n{inspirations}\n\nScales:\n{scales}\n\nMelody:\n{melody_instruments}\n\nChords:\n{chord_instruments}'

    result = build_llm_prompt_from_title(
        template=template,
        title="Tip of the Fatberg",
        inspirations=["lo-fi jazz"],
        scales=[{"name": "Major", "origin": "Western", "intervals": [0, 2, 4, 5, 7, 9, 11]}],
        instruments={"melody": [{"program": 0, "name": "Piano"}], "chords": [{"program": 19, "name": "Organ"}]},
    )

    assert '"Tip of the Fatberg"' in result
    assert "lo-fi jazz" in result
    assert "Major" in result
    assert "0: Piano" in result
    assert "19: Organ" in result


def test_build_llm_prompt_from_title_no_inspirations():
    """Handles empty inspirations list."""
    template = '{title}\n{inspirations}\n{scales}\n{melody_instruments}\n{chord_instruments}'

    result = build_llm_prompt_from_title(
        template=template,
        title="test",
        inspirations=[],
        scales=[{"name": "X", "origin": "Y", "intervals": [0, 2, 4]}],
        instruments={"melody": [{"program": 0, "name": "P"}], "chords": [{"program": 1, "name": "Q"}]},
    )

    assert "(none)" in result
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd midi-bot && python -m pytest tests/test_generator_title.py -v`

Expected: FAIL — `ImportError: cannot import name 'build_llm_prompt_from_title'`

- [ ] **Step 4: Add `build_llm_prompt_from_title` to generator.py**

Add this function after the existing `build_llm_prompt` (after line 97 in `midi-bot/src/generator.py`):

```python
def build_llm_prompt_from_title(
    template: str,
    title: str,
    inspirations: list[str],
    scales: list[dict],
    instruments: dict[str, list[dict]],
) -> str:
    """Build prompt with a song title as the primary seed (no headlines)."""
    inspirations_text = "\n".join(f"- {i}" for i in inspirations) if inspirations else "(none)"
    scales_lines = []
    for i, s in enumerate(scales, 1):
        desc = describe_scale(s)
        scales_lines.append(f'{i}. "{s["name"]}" — {s["origin"]}, {desc}')
    scales_text = "\n".join(scales_lines)
    melody_text = "\n".join(f"- {i['program']}: {i['name']}" for i in instruments["melody"])
    chords_text = "\n".join(f"- {i['program']}: {i['name']}" for i in instruments["chords"])

    return template.format(
        title=title,
        inspirations=inspirations_text,
        scales=scales_text,
        melody_instruments=melody_text,
        chord_instruments=chords_text,
    )
```

- [ ] **Step 5: Refactor `generate_music_params` to support both modes**

Modify the function signature at line 176 to accept optional `song_title` and make `headlines` optional:

```python
def generate_music_params(
    inspirations: list[str],
    scales: list[dict],
    instruments: dict[str, list[dict]],
    model: str,
    temperature: float,
    api_key: str,
    headlines: list[str] | None = None,
    song_title: str | None = None,
    template_path: Path = None,
) -> dict[str, Any]:
    """Generate structured music parameters via LLM.

    Exactly one of headlines or song_title must be provided.
    """
    client = InferenceClient(token=api_key)

    if song_title:
        if template_path is None:
            template_path = Path(__file__).parent.parent / "prompt_template_song_title.txt"
        system_prompt, user_template = load_template(template_path)
        user_prompt = build_llm_prompt_from_title(
            user_template, song_title, inspirations, scales, instruments
        )
    else:
        if template_path is None:
            template_path = Path(__file__).parent.parent / "prompt_template.txt"
        system_prompt, user_template = load_template(template_path)
        user_prompt = build_llm_prompt(
            user_template, headlines or [], inspirations, scales, instruments
        )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    response = client.chat_completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=1000,
    )

    result_text = response.choices[0].message.content.strip()
    logger.info(f"LLM response: {result_text[:200]}")

    params = parse_llm_response(result_text)
    validate_params(params, scales, instruments)

    return params
```

- [ ] **Step 6: Run tests to verify everything passes**

Run: `cd midi-bot && python -m pytest tests/ -v`

Expected: All tests PASS (existing + new)

- [ ] **Step 7: Update existing prompt template to remove "surrealist"**

In `midi-bot/prompt_template.txt`:
- Line 1: Change `"You are a surrealist composer with severe internet brain rot."` to `"You are a composer with severe internet brain rot."`
- Line 11: Change `"a single surreal sentence inspired by the headlines"` to `"a single weird sentence inspired by the headlines"`

- [ ] **Step 8: Commit**

```bash
git add midi-bot/prompt_template_song_title.txt midi-bot/src/generator.py midi-bot/prompt_template.txt midi-bot/tests/test_generator_title.py
git commit -m "feat(midi-bot): add song-title prompt mode and refactor generator

New prompt_template_song_title.txt uses song title as primary creative
seed. generator.py now accepts either headlines or song_title param.
Also removes 'surrealist' from existing headlines prompt to avoid
cliché melted-clock-style output."
```

---

### Task 8: midi-bot — Config + orchestrator changes

**Files:**
- Modify: `midi-bot/src/config.py:8-25` (add seed_source, song_titles_path defaults)
- Modify: `midi-bot/bot.py:84-142` (branch on seed_source)

- [ ] **Step 1: Update DEFAULT_CONFIG in config.py**

Add to the `DEFAULT_CONFIG` dict in `midi-bot/src/config.py`:

```python
DEFAULT_CONFIG = {
    "slack": {
        "channel": "#midieval",
    },
    "prompt": {
        "temperature": 1.0,
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "max_headlines": 10,
    },
    "inspirations": {
        "file": "inspirations.txt",
        "pick_count": 2,
    },
    "sources": [
        "reuters", "foxnews", "cnn", "bbc",
        "ft", "npr", "guardian", "breitbart"
    ],
    "seed_source": "song-titles",
    "song_titles_path": "../song-titles-bot/titles.json",
}
```

- [ ] **Step 2: Add `--seed-source` CLI arg to bot.py**

In `midi-bot/bot.py`, add to the argument parser (after line 202):

```python
parser.add_argument("--seed-source", choices=["song-titles", "headlines"],
                    help="Override seed source (default from config)")
```

And update `merge_cli_args` in `config.py`:

```python
if hasattr(args, 'seed_source') and args.seed_source:
    config["seed_source"] = args.seed_source
```

- [ ] **Step 3: Update `run_bot` to branch on seed_source**

Replace the headline-scraping and LLM-calling sections of `run_bot` (lines 102-142):

```python
    # Select creative seed based on config
    seed_source = config.get("seed_source", "song-titles")
    song_title_entry = None

    if seed_source == "song-titles":
        from src.title_selector import select_title
        titles_path = script_dir / config["song_titles_path"]
        used_path = script_dir / "used-song-titles.json"
        song_title_entry = select_title(titles_path, used_path)

        if not song_title_entry:
            logger.warning("No song titles available, falling back to headlines")
            seed_source = "headlines"
        else:
            logger.info(f"Song title: \"{song_title_entry['title']}\"")

    headlines = None
    if seed_source == "headlines":
        # Scrape headlines (reusing surreal-prompt-bot scraper)
        logger.info(f"Scraping headlines from {len(config['sources'])} sources...")
        headlines = scrape_all_sources(config["sources"])
        if not headlines:
            logger.error("No headlines scraped from any source")
            return 1
        max_headlines = config["prompt"]["max_headlines"]
        if len(headlines) > max_headlines:
            headlines = random.sample(headlines, max_headlines)
        logger.info(f"Using {len(headlines)} headlines")

    # Sample musical inspirations
    inspirations = []
    if config["inspirations"]["pick_count"] > 0:
        insp_path = script_dir / config["inspirations"]["file"]
        all_inspirations = load_inspirations(insp_path)
        inspirations = sample_inspirations(
            all_inspirations, config["inspirations"]["pick_count"]
        )
        logger.info(f"Using inspirations: {inspirations}")

    # Load scales + instruments databases
    scales = load_scales(script_dir / "scales.json")
    instruments = load_instruments(script_dir / "instruments.json")
    llm_scales = random.sample(scales, min(5, len(scales)))

    # Generate music parameters via LLM
    logger.info("Generating music parameters via LLM...")
    generate_kwargs = {
        "inspirations": inspirations,
        "scales": llm_scales,
        "instruments": instruments,
        "model": config["prompt"]["model"],
        "temperature": config["prompt"]["temperature"],
        "api_key": hf_token,
    }
    if song_title_entry:
        generate_kwargs["song_title"] = song_title_entry["title"]
    else:
        generate_kwargs["headlines"] = headlines

    params = generate_music_params(**generate_kwargs)

    # Attach song title to params for Slack poster
    if song_title_entry:
        params["song_title"] = song_title_entry["title"]

    logger.info(f"Music params: {json.dumps(params, indent=2)}")
```

- [ ] **Step 4: Update config.yaml**

Add to `midi-bot/config.yaml`:

```yaml
seed_source: "song-titles"
song_titles_path: "../song-titles-bot/titles.json"
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `cd midi-bot && python -m pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add midi-bot/src/config.py midi-bot/bot.py midi-bot/config.yaml
git commit -m "feat(midi-bot): add song-titles seed source with headlines fallback

Config defaults to seed_source=song-titles. When active, picks a
random unused title from song-titles-bot/titles.json and skips
headline scraping entirely. Falls back to headlines if titles.json
is missing or empty. CLI --seed-source flag for easy switching."
```

---

### Task 9: midi-bot — Slack poster format change

**Files:**
- Modify: `midi-bot/src/slack_poster.py:25-40` (add song title as first line)
- Create: `midi-bot/tests/test_slack_poster_title.py`

- [ ] **Step 1: Write the failing test**

```python
# midi-bot/tests/test_slack_poster_title.py
"""Tests for Slack poster song title formatting."""
from src.slack_poster import format_message


def test_format_message_with_song_title():
    """Song title appears as bold first line."""
    params = {
        "scale": "Major",
        "root": "C",
        "tempo": 120,
        "description": "test description",
        "melody_instrument": 0,
        "chord_instrument": 19,
        "temperature": 1.0,
        "chords": ["Cm", "Dm", "Em", "Fm"],
        "song_title": "Tip of the Fatberg",
    }
    instruments = {
        "melody": [{"program": 0, "name": "Piano"}],
        "chords": [{"program": 19, "name": "Church Organ"}],
    }

    msg = format_message(params, instruments)

    lines = msg.split("\n")
    assert lines[0] == '*"Tip of the Fatberg"*'
    assert "*Daily MIDI*" in lines[1]


def test_format_message_without_song_title():
    """No title line when song_title is absent (headlines mode)."""
    params = {
        "scale": "Minor",
        "root": "A",
        "tempo": 90,
        "description": "test",
        "melody_instrument": 0,
        "chord_instrument": 19,
        "temperature": 1.0,
        "chords": ["Am", "Dm", "Em", "Am"],
    }
    instruments = {
        "melody": [{"program": 0, "name": "Piano"}],
        "chords": [{"program": 19, "name": "Church Organ"}],
    }

    msg = format_message(params, instruments)

    lines = msg.split("\n")
    assert "*Daily MIDI*" in lines[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd midi-bot && python -m pytest tests/test_slack_poster_title.py -v`

Expected: FAIL (first test — song_title not handled)

- [ ] **Step 3: Update format_message**

In `midi-bot/src/slack_poster.py`, modify `format_message` (line 25):

```python
def format_message(params: dict, instruments: dict) -> str:
    """Format the main Slack message with all metadata."""
    melody_name = _find_instrument_name(params["melody_instrument"], instruments["melody"])
    chord_name = _find_instrument_name(params["chord_instrument"], instruments["chords"])
    chords_str = "  ".join(params["chords"])

    lines = []

    # Song title as bold first line (when using song-titles mode)
    if params.get("song_title"):
        lines.append(f'*"{params["song_title"]}"*')

    lines.extend([
        f":musical_note: *Daily MIDI* — {params['scale']} in {params['root']} ({params['tempo']} BPM)",
        f"_{params['description']}_",
        "",
        f":musical_keyboard: Melody — ImprovRNN, {melody_name} (MIDI {params['melody_instrument']}), temperature {params['temperature']}",
        f":drum_with_drumsticks: Drums — DrumsRNN, temperature {params['temperature']}",
        f":guitar: Bass — Programmatic from chord roots",
        f":musical_score: Chords — {chords_str}",
    ])
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd midi-bot && python -m pytest tests/test_slack_poster_title.py -v`

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add midi-bot/src/slack_poster.py midi-bot/tests/test_slack_poster_title.py
git commit -m "feat(midi-bot): add song title as bold first line in Slack messages

When song_title is present in params, it appears as the first line
in bold quotes. Headlines mode (no song_title) is unchanged."
```

---

## Chunk 3: glottisdale-bot + hymnal-bot Changes

### Task 10: glottisdale-bot — Title selection, seed derivation, Slack format

**Files:**
- Modify: `glottisdale-bot/bot.py:42-53,91-135` (add title selection, derive seed, pass to poster)
- Modify: `glottisdale-bot/glottisdale_slack/post.py:54-73` (add song title to message)
- Create: `glottisdale-bot/src/__init__.py` (empty)
- Create: `glottisdale-bot/src/title_selector.py` (duplicate of midi-bot version)
- Create: `glottisdale-bot/tests/test_title_integration.py`

- [ ] **Step 1: Copy title_selector.py from midi-bot**

Duplicate `midi-bot/src/title_selector.py` to `glottisdale-bot/src/title_selector.py`. The code is identical (~40 lines).

```bash
mkdir -p glottisdale-bot/src glottisdale-bot/tests
touch glottisdale-bot/src/__init__.py glottisdale-bot/tests/__init__.py
cp midi-bot/src/title_selector.py glottisdale-bot/src/title_selector.py
```

- [ ] **Step 2: Write the failing test**

```python
# glottisdale-bot/tests/test_title_integration.py
"""Test song title integration in glottisdale-bot."""
import hashlib
import json
from pathlib import Path


def test_seed_derivation():
    """Title hash produces a deterministic integer seed."""
    title = "Tip of the Fatberg"
    seed = int(hashlib.sha256(title.encode()).hexdigest()[:8], 16)

    # Same title always produces same seed
    seed2 = int(hashlib.sha256(title.encode()).hexdigest()[:8], 16)
    assert seed == seed2

    # Different title produces different seed
    seed3 = int(hashlib.sha256("sleep cartel".encode()).hexdigest()[:8], 16)
    assert seed != seed3

    # Seed is a positive integer
    assert seed > 0
    assert isinstance(seed, int)
```

- [ ] **Step 3: Run test to verify it passes** (this is a pure logic test)

Run: `cd glottisdale-bot && python -m pytest tests/test_title_integration.py -v`

Expected: PASS

- [ ] **Step 4: Modify bot.py to add title selection and seed derivation**

In `glottisdale-bot/bot.py`, add imports at the top:

```python
import hashlib
sys.path.insert(0, str(Path(__file__).parent))
from src.title_selector import select_title
```

In `main()`, after fetching videos (line 111) and before calling `run_glottisdale_cli` (line 112), add title selection:

```python
        # Select song title for labeling and seed derivation
        script_dir = Path(__file__).parent
        titles_path = script_dir / "../song-titles-bot/titles.json"
        used_path = script_dir / "used-song-titles.json"
        song_title_entry = select_title(titles_path, used_path)

        song_title = None
        if song_title_entry:
            song_title = song_title_entry["title"]
            logger.info(f"Song title: \"{song_title}\"")

            # Derive deterministic seed from title (if no explicit seed given)
            if args.seed is None:
                args.seed = int(hashlib.sha256(song_title.encode()).hexdigest()[:8], 16)
                logger.info(f"Derived seed from title: {args.seed}")
```

In the `post_results` call (line 127), add `song_title`:

```python
            post_results(
                token=token,
                channel=args.dest_channel,
                concatenated_path=info["output"],
                run_dir=info["run_dir"],
                clip_count=info["clip_count"],
                sources=videos,
                source_clip_counts=source_clip_counts,
                song_title=song_title,
            )
```

- [ ] **Step 5: Modify post.py to include song title**

In `glottisdale-bot/glottisdale_slack/post.py`, update `post_results` signature (line 54) to accept `song_title: str | None = None`:

```python
def post_results(
    token: str,
    channel: str,
    concatenated_path: Path,
    run_dir: Path,
    clip_count: int,
    sources: list[dict],
    source_clip_counts: dict[str, int] | None = None,
    song_title: str | None = None,
    _client: WebClient | None = None,
) -> None:
```

Update the summary line (line 73):

```python
    lines = []
    if song_title:
        lines.append(f'*"{song_title}"*')
    lines.append(f":scissors: *Glottisdale* — {clip_count} words from {len(sources)} source(s)")
    summary = "\n".join(lines)
```

- [ ] **Step 6: Run tests**

Run: `cd glottisdale-bot && python -m pytest tests/ -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add glottisdale-bot/src/ glottisdale-bot/tests/ glottisdale-bot/bot.py glottisdale-bot/glottisdale_slack/post.py
git commit -m "feat(glottisdale-bot): integrate song titles as seed and label

Picks random unused title from song-titles-bot/titles.json.
Hashes title into deterministic --seed for glottisdale CLI.
Adds song title as bold first line in Slack messages.
Explicit --seed from workflow dispatch takes precedence."
```

---

### Task 11: hymnal-bot — Parser tweak + Slack format

**Files:**
- Modify: `hymnal-bot/slack_fetcher.py:17-49` (guard description regex, extract song title)
- Modify: `hymnal-bot/slack_poster.py:11-26` (add song title as first line)

- [ ] **Step 1: Update parse_midi_message in slack_fetcher.py**

The existing `re.search()` on `*Daily MIDI*` already scans full text, so it works when the title is line 1. But the description regex `r'_(.+?)_'` could match content before `*Daily MIDI*` if a title contains underscores. Guard it:

```python
def parse_midi_message(text: str) -> dict | None:
    """Parse a Daily MIDI bot message into metadata."""
    header = re.search(
        r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)', text
    )
    if not header:
        return None

    scale = header.group(1).strip()
    root = header.group(2)
    tempo = int(header.group(3))

    # Search for description only AFTER the *Daily MIDI* header
    text_after_header = text[header.end():]
    desc_match = re.search(r'_(.+?)_', text_after_header)
    description = desc_match.group(1) if desc_match else ""

    chords_match = re.search(r'Chords\s*—\s*(.+?)(?:\n|$)', text)
    chords = chords_match.group(1).split() if chords_match else []

    inst_match = re.search(r'MIDI\s+(\d+)', text)
    melody_instrument = int(inst_match.group(1)) if inst_match else 0

    temp_match = re.search(r'temperature\s+([\d.]+)', text)
    temperature = float(temp_match.group(1)) if temp_match else 1.0

    # Extract song title from first line (if present)
    title_match = re.match(r'^\*"(.+?)"\*', text)
    song_title = title_match.group(1) if title_match else None

    result = {
        "scale": scale,
        "root": root,
        "tempo": tempo,
        "description": description,
        "chords": chords,
        "melody_instrument": melody_instrument,
        "temperature": temperature,
    }
    if song_title:
        result["song_title"] = song_title

    return result
```

- [ ] **Step 2: Update hymnal slack_poster.py**

In `hymnal-bot/slack_poster.py`, modify `format_message` (line 11):

```python
def format_message(
    scale: str,
    root: str,
    tempo: int,
    description: str,
    source_link: str,
    song_title: str | None = None,
) -> str:
    """Format the Slack message for posting."""
    lines = []
    if song_title:
        lines.append(f'*"{song_title}"*')
    lines.append(f":microphone: *Hymnal Gargler* — {scale} in {root} ({tempo} BPM)")
    if description:
        lines.append(f"_{description}_")
    lines.append("")
    lines.append(f"Source: <{source_link}|#midieval>")
    return "\n".join(lines)
```

Update the call site in `post_results` (line 46) to pass `song_title`:

```python
    message = format_message(
        scale=metadata["scale"],
        root=metadata["root"],
        tempo=metadata["tempo"],
        description=metadata.get("description", ""),
        source_link=source_link,
        song_title=metadata.get("song_title"),
    )
```

- [ ] **Step 3: Verify no regressions**

Run: `cd hymnal-bot && python -m pytest tests/ -v` (if tests exist)

Otherwise, verify manually: `python -c "from slack_fetcher import parse_midi_message; print(parse_midi_message('*\"Tip\"*\n:musical_note: *Daily MIDI* — Major in C (120 BPM)\n_desc_'))"`

Expected: Dict with `song_title: "Tip"`, `scale: "Major"`, `description: "desc"`

- [ ] **Step 4: Commit**

```bash
git add hymnal-bot/slack_fetcher.py hymnal-bot/slack_poster.py
git commit -m "feat(hymnal-bot): extract and display song title from Daily MIDI

Guards description regex to only match after *Daily MIDI* header,
preventing false matches from song titles with underscores.
Extracts song title from first line and includes it as bold first
line in Hymnal Gargler Slack messages."
```

---

## Chunk 4: GitHub Actions + Cleanup

### Task 12: GitHub Actions — New song-titles workflow

**Files:**
- Create: `.github/workflows/song-titles.yml`

- [ ] **Step 1: Create the workflow**

```yaml
# .github/workflows/song-titles.yml
name: Song Titles Bot

on:
  schedule:
    - cron: '0 5 * * *'  # 5am UTC daily (before midi-bot and glottisdale)
  workflow_dispatch:

jobs:
  update-song-titles:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r song-titles-bot/requirements.txt

      - name: Run song titles bot
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: python song-titles-bot/bot.py

      - name: Commit changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add song-titles-bot/titles.json this-song-is-a-junkyard.html
          git diff --staged --quiet || git commit -m "chore: update song titles ($(date +%Y-%m-%d)) [skip ci]"
          git push
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/song-titles.yml
git commit -m "ci: add daily song-titles bot workflow

Runs at 5am UTC (before midi-bot and glottisdale), scrapes
#song-titles, filters via HF API, updates titles.json,
regenerates this-song-is-a-junkyard.html."
```

---

### Task 13: Update existing workflows to commit used-song-titles.json

**Files:**
- Modify: `.github/workflows/daily-midi.yml` (add commit step for used-song-titles.json)
- Modify: `.github/workflows/glottisdale.yml` (add commit step for used-song-titles.json)

The `used-song-titles.json` files must be committed so usage tracking persists across CI runs.

- [ ] **Step 1: Update daily-midi.yml**

Add a commit step after the bot runs:

```yaml
      - name: Commit usage tracking
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add midi-bot/used-song-titles.json
          git diff --staged --quiet || git commit -m "chore: update midi-bot song title usage [skip ci]"
          git push
```

- [ ] **Step 2: Update glottisdale.yml**

Add a similar commit step:

```yaml
      - name: Commit usage tracking
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add glottisdale-bot/used-song-titles.json
          git diff --staged --quiet || git commit -m "chore: update glottisdale song title usage [skip ci]"
          git push
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily-midi.yml .github/workflows/glottisdale.yml
git commit -m "ci: commit used-song-titles.json from midi-bot and glottisdale workflows

Usage tracking files must persist across CI runs so titles aren't
repeated. Both workflows now commit their used-song-titles.json."
```

---

### Task 14: Cleanup — Remove deprecated files

**Files:**
- Remove: `songtitles.html`
- Remove: `slack-song-generator/` (entire directory)

- [ ] **Step 1: Remove files**

```bash
git rm songtitles.html
git rm -r slack-song-generator/
```

- [ ] **Step 2: Verify no broken references**

Search for any remaining references to `songtitles.html` or `slack-song-generator`:

```bash
grep -r "songtitles.html" --include="*.html" --include="*.md" --include="*.py" --include="*.yml" .
grep -r "slack-song-generator" --include="*.html" --include="*.md" --include="*.py" --include="*.yml" .
```

Fix any references found (likely in `index.html` if there's a link, and `docs/README.md` which was already updated).

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove deprecated songtitles.html and slack-song-generator/

Replaced by song-titles-bot/ which generates this-song-is-a-junkyard.html
directly. See docs/plans/2026-03-13-song-title-integration-design.md."
```

---

## Summary

| Task | Component | Key Files |
|------|-----------|-----------|
| 1 | Migration | `song-titles-bot/titles.json` |
| 2 | Scraper | `song-titles-bot/src/slack_scraper.py` |
| 3 | Filter | `song-titles-bot/src/filter.py` |
| 4 | HTML gen | `song-titles-bot/src/html_generator.py`, `templates/junkyard.html.j2` |
| 5 | Orchestrator | `song-titles-bot/bot.py`, `config.yaml` |
| 6 | Title selector | `midi-bot/src/title_selector.py` |
| 7 | Prompt refactor | `midi-bot/src/generator.py`, `prompt_template_song_title.txt` |
| 8 | Config/orchestrator | `midi-bot/bot.py`, `config.yaml` |
| 9 | Slack format | `midi-bot/src/slack_poster.py` |
| 10 | Glottisdale | `glottisdale-bot/bot.py`, `post.py`, `title_selector.py` |
| 11 | Hymnal | `hymnal-bot/slack_fetcher.py`, `slack_poster.py` |
| 12 | CI: song-titles | `.github/workflows/song-titles.yml` |
| 13 | CI: usage tracking | `.github/workflows/daily-midi.yml`, `glottisdale.yml` |
| 14 | Cleanup | Remove `songtitles.html`, `slack-song-generator/` |

**Dependencies:** Tasks 1-5 (song-titles-bot) → Tasks 6-9 (midi-bot) and Task 10 (glottisdale) can run in parallel → Task 11 (hymnal) → Tasks 12-14 (CI + cleanup).

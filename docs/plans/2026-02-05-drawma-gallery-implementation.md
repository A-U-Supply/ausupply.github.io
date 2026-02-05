# Drawma Gallery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily-updating gallery of surrealist drawings from the #drawma Slack channel, displayed as a dark Twin Peaks-themed slideshow, with a link from the homepage.

**Architecture:** A Python scraper fetches images from Slack and saves them with metadata to `img/drawma/`. A standalone HTML page reads a manifest JSON and displays images one at a time with fade transitions. A GitHub Action runs the scraper daily and commits new images.

**Tech Stack:** Python 3.11+, slack-sdk (already in requirements), HTML/CSS/JS (vanilla), GitHub Actions

**Working directory:** `.worktrees/drawma-gallery`

**Design doc:** `docs/plans/2026-02-05-drawma-gallery-design.md`

---

### Task 1: Create img/drawma/ Directory and Seed Manifest

**Files:**
- Create: `img/drawma/manifest.json`

**Step 1: Create directory and empty manifest**

```bash
mkdir -p img/drawma
```

Create `img/drawma/manifest.json`:

```json
[]
```

**Step 2: Commit**

```bash
git add img/drawma/manifest.json
git commit -m "feat: create img/drawma/ directory with empty manifest"
```

---

### Task 2: Resize drawma-icon.png for Homepage

**Files:**
- Modify: `img/drawma-icon.png` (resize from 1080x891 to ~200px wide)

The icon is 1080x891 — way too large for a homepage draggable icon. Resize it down to 200px wide (proportional height ~165px) to match the scale of other homepage elements like `img/herstory.png`.

**Step 1: Resize the image**

```bash
sips --resampleWidth 200 img/drawma-icon.png
```

**Step 2: Verify the new size**

```bash
sips -g pixelWidth -g pixelHeight img/drawma-icon.png
```

Expected: pixelWidth: 200, pixelHeight: ~165

**Step 3: Commit**

```bash
git add img/drawma-icon.png
git commit -m "feat: resize drawma-icon.png to 200px for homepage use"
```

---

### Task 3: Write the Slack Image Scraper — Tests

**Files:**
- Create: `surreal-prompt-bot/tests/test_scrape_gallery.py`

**Step 1: Write the tests**

These tests cover the core scraper logic: identifying images in messages, associating images with prompts, deduplication via manifest, and file downloading.

```python
"""Tests for Slack gallery image scraper."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scrape_gallery import (
    get_bot_user_id,
    fetch_channel_messages,
    extract_images_from_messages,
    associate_images_with_prompts,
    download_image,
    filter_new_images,
)


def _make_message(text="hello", ts="1700000000.000000", user="U123", files=None, bot_id=None, reply_count=0):
    """Helper to create a Slack message dict."""
    msg = {"text": text, "ts": ts, "user": user, "type": "message"}
    if files:
        msg["files"] = files
    if bot_id:
        msg["bot_id"] = bot_id
    if reply_count:
        msg["reply_count"] = reply_count
    return msg


def _make_file(file_id="F001", name="drawing.png", mimetype="image/png"):
    """Helper to create a Slack file dict."""
    return {
        "id": file_id,
        "name": name,
        "mimetype": mimetype,
        "url_private_download": f"https://files.slack.com/files-pri/{file_id}/{name}",
        "original_w": 800,
        "original_h": 600,
    }


def test_extract_images_finds_image_files():
    """Extracts image files from messages, ignores non-images."""
    messages = [
        _make_message(files=[_make_file("F001", "art.png", "image/png")]),
        _make_message(files=[_make_file("F002", "doc.pdf", "application/pdf")]),
        _make_message(text="no files here"),
        _make_message(files=[
            _make_file("F003", "sketch.jpg", "image/jpeg"),
            _make_file("F004", "photo.gif", "image/gif"),
        ]),
    ]

    images = extract_images_from_messages(messages)

    file_ids = [img["file"]["id"] for img in images]
    assert "F001" in file_ids
    assert "F002" not in file_ids  # PDF excluded
    assert "F003" in file_ids
    assert "F004" in file_ids
    assert len(images) == 3


def test_extract_images_includes_message_metadata():
    """Each extracted image carries its parent message's timestamp and user."""
    messages = [
        _make_message(
            ts="1700000000.000000",
            user="UARTIST",
            files=[_make_file("F001")],
        ),
    ]

    images = extract_images_from_messages(messages)

    assert images[0]["message_ts"] == "1700000000.000000"
    assert images[0]["user"] == "UARTIST"


def test_associate_images_with_prompts_same_day():
    """Images posted same day as a bot prompt get associated with it."""
    # Bot prompt at 2026-02-03 10:00 UTC
    prompt_ts = "1738573200.000000"
    # Image posted same day at 2026-02-03 15:00 UTC
    image_ts = "1738591200.000000"

    prompts = [{"ts": prompt_ts, "text": "Draw a fish 🐟"}]
    images = [{"file": _make_file("F001"), "message_ts": image_ts, "user": "UARTIST"}]

    associated = associate_images_with_prompts(images, prompts)

    assert associated[0]["prompt"] == "Draw a fish 🐟"


def test_filter_new_images_skips_existing():
    """Images already in manifest are skipped."""
    existing_manifest = [{"id": "F001", "filename": "2026-02-03-F001.png"}]
    images = [
        {"file": _make_file("F001"), "message_ts": "1700000000.000000", "user": "U1"},
        {"file": _make_file("F002"), "message_ts": "1700000000.000000", "user": "U2"},
    ]

    new_images = filter_new_images(images, existing_manifest)

    assert len(new_images) == 1
    assert new_images[0]["file"]["id"] == "F002"


def test_download_image_saves_file():
    """Downloads image to correct path with expected filename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        image = {
            "file": _make_file("F001", "art.png", "image/png"),
            "message_ts": "1738573200.000000",  # 2025-02-03
            "user": "UARTIST",
            "prompt": "Draw a fish",
        }

        mock_response = MagicMock()
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()

        with patch("scrape_gallery.requests.get", return_value=mock_response):
            entry = download_image(image, output_dir, "xoxb-test-token")

        assert entry["id"] == "F001"
        assert entry["filename"].endswith(".png")
        assert (output_dir / entry["filename"]).exists()
        assert entry["prompt"] == "Draw a fish"
```

**Step 2: Run tests to verify they fail**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_scrape_gallery.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scrape_gallery'"

**Step 3: Commit tests**

```bash
git add surreal-prompt-bot/tests/test_scrape_gallery.py
git commit -m "test: add failing tests for drawma gallery scraper"
```

---

### Task 4: Write the Slack Image Scraper — Implementation

**Files:**
- Create: `surreal-prompt-bot/scrape_gallery.py`

**Step 1: Write the scraper**

```python
#!/usr/bin/env python3
"""Scrape images from #drawma Slack channel and save to img/drawma/."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from slack_sdk import WebClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Channel name to scrape
CHANNEL_NAME = "#drawma"


def get_bot_user_id(client: WebClient) -> str:
    """Get the bot's own user ID to identify prompt messages."""
    response = client.auth_test()
    return response["user_id"]


def find_channel_id(client: WebClient, channel_name: str) -> str:
    """Find channel ID by name."""
    name = channel_name.lstrip("#")
    cursor = None
    while True:
        response = client.conversations_list(cursor=cursor, limit=200)
        for channel in response["channels"]:
            if channel["name"] == name:
                return channel["id"]
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"Channel {channel_name} not found")


def fetch_channel_messages(client: WebClient, channel_id: str, days_back: int = 7) -> list[dict]:
    """Fetch recent messages from channel."""
    oldest = datetime.now(timezone.utc).timestamp() - (days_back * 86400)
    messages = []
    cursor = None
    while True:
        response = client.conversations_history(
            channel=channel_id, oldest=str(oldest), cursor=cursor, limit=200,
        )
        messages.extend(response.get("messages", []))
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages


def fetch_thread_replies(client: WebClient, channel_id: str, thread_ts: str) -> list[dict]:
    """Fetch replies in a thread."""
    response = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=200)
    # First message is the parent, skip it
    return response.get("messages", [])[1:]


def extract_images_from_messages(messages: list[dict]) -> list[dict]:
    """Extract image file references from messages."""
    images = []
    for msg in messages:
        if "files" not in msg:
            continue
        for f in msg["files"]:
            if f.get("mimetype", "").startswith("image/"):
                images.append({
                    "file": f,
                    "message_ts": msg["ts"],
                    "user": msg.get("user", "unknown"),
                })
    return images


def associate_images_with_prompts(images: list[dict], prompts: list[dict]) -> list[dict]:
    """Associate each image with the prompt from the same day."""
    # Build date -> prompt mapping
    prompt_by_date = {}
    for p in prompts:
        dt = datetime.fromtimestamp(float(p["ts"]), tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        prompt_by_date[date_str] = p["text"]

    for img in images:
        dt = datetime.fromtimestamp(float(img["message_ts"]), tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        img["prompt"] = prompt_by_date.get(date_str, "")
        img["date"] = date_str

    return images


def filter_new_images(images: list[dict], manifest: list[dict]) -> list[dict]:
    """Filter out images already in the manifest."""
    existing_ids = {entry["id"] for entry in manifest}
    return [img for img in images if img["file"]["id"] not in existing_ids]


def download_image(image: dict, output_dir: Path, token: str) -> dict:
    """Download a single image and return a manifest entry."""
    f = image["file"]
    ext = f["name"].rsplit(".", 1)[-1] if "." in f["name"] else "png"
    date_str = image.get("date", "unknown")
    filename = f"{date_str}-{f['id']}.{ext}"

    url = f["url_private_download"]
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    response.raise_for_status()

    filepath = output_dir / filename
    filepath.write_bytes(response.content)
    logger.info(f"Downloaded {filename} ({len(response.content)} bytes)")

    return {
        "id": f["id"],
        "filename": filename,
        "date": date_str,
        "prompt": image.get("prompt", ""),
        "artist": image.get("user", "unknown"),
        "width": f.get("original_w", 0),
        "height": f.get("original_h", 0),
    }


def get_slack_username(client: WebClient, user_id: str) -> str:
    """Look up a Slack user's display name."""
    try:
        response = client.users_info(user=user_id)
        profile = response["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        return user_id


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    # Paths relative to repo root
    repo_root = Path(__file__).parent.parent
    output_dir = repo_root / "img" / "drawma"
    manifest_path = output_dir / "manifest.json"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load existing manifest
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = []

    client = WebClient(token=token)

    # Find channel and bot user
    bot_user_id = get_bot_user_id(client)
    channel_id = find_channel_id(client, CHANNEL_NAME)
    logger.info(f"Bot user ID: {bot_user_id}, Channel ID: {channel_id}")

    # Fetch messages
    messages = fetch_channel_messages(client, channel_id, days_back=7)
    logger.info(f"Fetched {len(messages)} messages")

    # Identify bot prompts
    prompts = [m for m in messages if m.get("user") == bot_user_id or m.get("bot_id")]

    # Collect images from top-level messages
    all_images = extract_images_from_messages(messages)

    # Also collect images from threads under bot prompts
    for prompt in prompts:
        if prompt.get("reply_count", 0) > 0:
            replies = fetch_thread_replies(client, channel_id, prompt["ts"])
            thread_images = extract_images_from_messages(replies)
            all_images.extend(thread_images)

    logger.info(f"Found {len(all_images)} total images")

    # Associate with prompts and filter
    all_images = associate_images_with_prompts(all_images, prompts)
    new_images = filter_new_images(all_images, manifest)
    logger.info(f"New images to download: {len(new_images)}")

    if not new_images:
        logger.info("No new images found")
        return 0

    # Resolve Slack user IDs to display names
    user_cache = {}
    for img in new_images:
        uid = img["user"]
        if uid not in user_cache:
            user_cache[uid] = get_slack_username(client, uid)
        img["user"] = user_cache[uid]

    # Download and add to manifest
    for img in new_images:
        entry = download_image(img, output_dir, token)
        entry["artist"] = img["user"]
        manifest.append(entry)

    # Sort manifest by date descending
    manifest.sort(key=lambda e: e["date"], reverse=True)

    # Save manifest
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info(f"Manifest updated: {len(manifest)} total entries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Run tests to verify they pass**

```bash
cd surreal-prompt-bot && python -m pytest tests/test_scrape_gallery.py -v
```

Expected: PASS (5 tests)

**Step 3: Commit**

```bash
git add surreal-prompt-bot/scrape_gallery.py
git commit -m "feat: add Slack image scraper for drawma gallery"
```

---

### Task 5: Create the Gallery Page — drawma.html

**Files:**
- Create: `drawma.html`

**Step 1: Create the Twin Peaks gallery page**

This is a standalone dark page — no shared header, no vcfmw.css. Fully self-contained. Loads `img/drawma/manifest.json`, displays one image at a time with fade transitions, prompt revealed on click.

Key design elements:
- Black background, dark red accents (#8b0000)
- Serif font (Georgia)
- Chevron zig-zag pattern along bottom (CSS repeating-linear-gradient)
- Centered image with vignette/red border
- Slow fade transition between images (CSS opacity transition)
- Click left half = previous, click right half = next
- Arrow key navigation
- Click image = reveal prompt text (italic, fades in below)
- Subtle image counter
- Title with subtle flicker animation
- Preloads adjacent images

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DRAWMA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,700;1,400&display=swap');

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: #0a0a0a;
            color: #d4c5a9;
            font-family: 'EB Garamond', Georgia, serif;
            min-height: 100vh;
            overflow: hidden;
            cursor: default;
            position: relative;
        }

        /* Chevron floor */
        .floor {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: repeating-linear-gradient(
                135deg,
                #1a1a1a 0px, #1a1a1a 10px,
                #f5f5dc 10px, #f5f5dc 20px,
                #1a1a1a 20px, #1a1a1a 30px
            );
            opacity: 0.15;
            z-index: 0;
        }

        /* Title */
        .title {
            position: fixed;
            top: 20px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 1.4rem;
            letter-spacing: 0.5em;
            text-transform: uppercase;
            color: #8b0000;
            z-index: 10;
            animation: flicker 4s infinite;
        }

        @keyframes flicker {
            0%, 95%, 100% { opacity: 1; }
            96% { opacity: 0.4; }
            97% { opacity: 0.9; }
            98% { opacity: 0.3; }
            99% { opacity: 1; }
        }

        /* Image container */
        .gallery {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            width: 100vw;
            position: relative;
        }

        .image-frame {
            position: relative;
            max-width: 85vw;
            max-height: 75vh;
            border: 2px solid #8b0000;
            box-shadow: 0 0 40px rgba(139, 0, 0, 0.3), inset 0 0 30px rgba(0, 0, 0, 0.5);
        }

        .image-frame img {
            display: block;
            max-width: 85vw;
            max-height: 75vh;
            object-fit: contain;
            transition: opacity 0.8s ease;
        }

        .image-frame img.fading {
            opacity: 0;
        }

        /* Navigation zones */
        .nav-left, .nav-right {
            position: fixed;
            top: 0;
            bottom: 0;
            width: 40%;
            z-index: 5;
            cursor: pointer;
        }

        .nav-left {
            left: 0;
        }

        .nav-right {
            right: 0;
        }

        .nav-left:hover {
            cursor: w-resize;
        }

        .nav-right:hover {
            cursor: e-resize;
        }

        /* Prompt reveal */
        .prompt-text {
            position: fixed;
            bottom: 80px;
            left: 10%;
            right: 10%;
            text-align: center;
            font-style: italic;
            font-size: 1.2rem;
            color: #d4c5a9;
            opacity: 0;
            transition: opacity 0.6s ease;
            z-index: 10;
            text-shadow: 0 0 10px rgba(139, 0, 0, 0.5);
        }

        .prompt-text.visible {
            opacity: 1;
        }

        /* Counter */
        .counter {
            position: fixed;
            top: 20px;
            right: 30px;
            font-size: 0.85rem;
            color: #555;
            z-index: 10;
            letter-spacing: 0.1em;
        }

        /* Artist */
        .artist {
            position: fixed;
            bottom: 80px;
            right: 30px;
            font-size: 0.85rem;
            color: #555;
            z-index: 10;
            font-style: italic;
            opacity: 0;
            transition: opacity 0.6s ease;
        }

        .artist.visible {
            opacity: 1;
        }

        /* Loading state */
        .loading {
            color: #8b0000;
            font-size: 1.2rem;
            letter-spacing: 0.3em;
        }

        /* Home link */
        .home-link {
            position: fixed;
            top: 20px;
            left: 30px;
            font-size: 0.85rem;
            z-index: 10;
        }

        .home-link a {
            color: #555;
            text-decoration: none;
            transition: color 0.3s;
        }

        .home-link a:hover {
            color: #8b0000;
        }
    </style>
</head>
<body>
    <div class="title">Drawma</div>
    <div class="home-link"><a href="index.html">&larr; back</a></div>
    <div class="counter"></div>

    <div class="gallery">
        <div class="loading">. . .</div>
        <div class="image-frame" style="display: none;">
            <img src="" alt="">
        </div>
    </div>

    <div class="prompt-text"></div>
    <div class="artist"></div>

    <div class="nav-left"></div>
    <div class="nav-right"></div>

    <div class="floor"></div>

    <script>
        let manifest = [];
        let currentIndex = 0;
        let promptVisible = false;
        const preloaded = {};

        const img = document.querySelector('.image-frame img');
        const frame = document.querySelector('.image-frame');
        const loading = document.querySelector('.loading');
        const promptEl = document.querySelector('.prompt-text');
        const counterEl = document.querySelector('.counter');
        const artistEl = document.querySelector('.artist');

        function preloadImage(index) {
            if (index < 0 || index >= manifest.length) return;
            const entry = manifest[index];
            if (preloaded[entry.filename]) return;
            const preImg = new Image();
            preImg.src = 'img/drawma/' + entry.filename;
            preloaded[entry.filename] = preImg;
        }

        function showImage(index) {
            if (manifest.length === 0) return;
            currentIndex = ((index % manifest.length) + manifest.length) % manifest.length;
            const entry = manifest[currentIndex];

            // Hide prompt
            promptVisible = false;
            promptEl.classList.remove('visible');
            artistEl.classList.remove('visible');

            // Fade out
            img.classList.add('fading');

            setTimeout(function() {
                img.src = 'img/drawma/' + entry.filename;
                img.alt = entry.prompt || 'Untitled';
                img.onload = function() {
                    img.classList.remove('fading');
                };
                counterEl.textContent = (currentIndex + 1) + ' / ' + manifest.length;
                promptEl.textContent = entry.prompt || '';
                artistEl.textContent = entry.artist || '';

                // Preload neighbors
                preloadImage(currentIndex - 1);
                preloadImage(currentIndex + 1);
            }, 400);
        }

        function togglePrompt() {
            promptVisible = !promptVisible;
            if (promptVisible) {
                promptEl.classList.add('visible');
                artistEl.classList.add('visible');
            } else {
                promptEl.classList.remove('visible');
                artistEl.classList.remove('visible');
            }
        }

        // Navigation
        document.querySelector('.nav-left').addEventListener('click', function() {
            showImage(currentIndex - 1);
        });
        document.querySelector('.nav-right').addEventListener('click', function() {
            showImage(currentIndex + 1);
        });

        // Click image to reveal prompt
        frame.addEventListener('click', function(e) {
            e.stopPropagation();
            togglePrompt();
        });

        // Keyboard
        document.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft') {
                showImage(currentIndex - 1);
            } else if (e.key === 'ArrowRight') {
                showImage(currentIndex + 1);
            } else if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                togglePrompt();
            }
        });

        // Touch swipe support
        let touchStartX = 0;
        document.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
        });
        document.addEventListener('touchend', function(e) {
            const diff = e.changedTouches[0].clientX - touchStartX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) {
                    showImage(currentIndex - 1);
                } else {
                    showImage(currentIndex + 1);
                }
            }
        });

        // Load manifest
        fetch('img/drawma/manifest.json')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                manifest = data;
                if (manifest.length === 0) {
                    loading.textContent = 'No drawings yet';
                    return;
                }
                loading.style.display = 'none';
                frame.style.display = 'block';
                showImage(0);
            })
            .catch(function() {
                loading.textContent = 'The owls are not what they seem';
            });
    </script>
</body>
</html>
```

**Step 2: Verify the page loads locally**

Open `drawma.html` in a browser. Should show a dark page with "No drawings yet" (empty manifest) or ". . ." loading indicator. Verify the chevron floor, red title flicker, and dark aesthetic.

**Step 3: Commit**

```bash
git add drawma.html
git commit -m "feat: add Twin Peaks-themed drawma gallery page"
```

---

### Task 6: Add Homepage Link

**Files:**
- Modify: `index.html`

**Step 1: Add draggable drawma link to the homepage**

Add a new draggable element after the `timemachine` div (line 151) and before the `continue` div (line 153). Follow the same pattern as the history link — image wrapped in a link, with a `data-id` and initial position.

Find this block in `index.html`:

```html
<div class="draggable" data-id="timemachine" data-rotation="3"
     style="left: 70%; top: 10%; transform: rotate(3deg);">
    <a href="history.html"><img src="img/herstory.png" width="48" height="48"></a>
</div>
```

Add immediately after it:

```html
<div class="draggable" data-id="drawma" data-rotation="-4"
     style="left: 30%; top: 70%; transform: rotate(-4deg);">
    <a href="drawma.html"><img src="img/drawma-icon.png"></a>
</div>
```

No explicit width/height needed since the image was already resized to 200px in Task 2.

**Step 2: Verify locally**

Open `index.html` in a browser. Verify the drawma icon appears, is draggable, and links to `drawma.html`.

**Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add drawma gallery link to homepage"
```

---

### Task 7: Create GitHub Action Workflow

**Files:**
- Create: `.github/workflows/scrape-drawma.yml`

**Step 1: Create the workflow**

```yaml
name: Scrape Drawma Gallery Images

on:
  schedule:
    # 11pm PT = 7am UTC (during PST)
    - cron: '0 7 * * *'
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install slack-sdk requests

      - name: Scrape images from Slack
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        run: python surreal-prompt-bot/scrape_gallery.py

      - name: Commit new images
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add img/drawma/
          if git diff --cached --quiet; then
            echo "No new images to commit."
          else
            git commit -m "chore: add drawma gallery images ($(date -u +%Y-%m-%d)) [skip ci]"
            git push
          fi
```

**Step 2: Verify YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/scrape-drawma.yml'))"
```

Expected: No output (valid YAML)

**Step 3: Commit**

```bash
git add .github/workflows/scrape-drawma.yml
git commit -m "feat: add GitHub Action to scrape drawma images daily"
```

---

### Task 8: Update Design Doc Status

**Files:**
- Modify: `docs/plans/2026-02-05-drawma-gallery-design.md`

**Step 1: Update status to Implemented**

Change line 3 from:

```
**Status:** Approved
```

to:

```
**Status:** Implemented
```

**Step 2: Commit**

```bash
git add docs/plans/2026-02-05-drawma-gallery-design.md
git commit -m "docs: mark drawma gallery design as implemented"
```

---

## Post-Implementation

After all tasks complete:

1. **Add Slack scopes:** Add `channels:history` and `files:read` to the Slack app, reinstall to workspace
2. **Merge branch:** Use `superpowers:finishing-a-development-branch`
3. **Test workflow:** Use "Run workflow" button in GitHub Actions UI
4. **Verify gallery:** Check that drawma.html loads with downloaded images

## One-Time Slack Setup Required

| Scope | Purpose |
|-------|---------|
| `channels:history` | Read messages from #drawma |
| `files:read` | Download image files |

These are added in the Slack app config at https://api.slack.com/apps. After adding, reinstall the app to the workspace.

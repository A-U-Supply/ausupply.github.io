# Puke Box Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a geocities-inspired jukebox page that plays audio previews from the daily MIDI bot, with a Slack scraper to populate it.

**Architecture:** A Python scraper pulls #midieval messages from Slack, downloads MIDI files, synthesizes OGG previews, and commits to `puke-box/YYYY-MM-DD/`. A static HTML page reads a manifest and renders an interactive jukebox with overlaid controls on a stock photo.

**Tech Stack:** Python (slack-sdk, pretty_midi, scipy), ffmpeg (WAV→OGG), vanilla HTML/CSS/JS

---

### Task 1: Scraper — Slack message parsing

**Files:**
- Create: `puke-box/scrape_midieval.py`
- Create: `puke-box/tests/test_scraper.py`

The scraper connects to Slack, reads #midieval history, and parses "Daily MIDI" messages into structured metadata. Follow the drawma scraper pattern (`surreal-prompt-bot/scrape_gallery.py`) for Slack API calls, pagination, and file downloads.

**Step 1: Write failing tests for message parsing**

```python
# puke-box/tests/test_scraper.py
import pytest
from scrape_midieval import parse_midi_message


def test_parse_midi_message():
    """Parse metadata from a Daily MIDI Slack message."""
    text = (
        ":musical_note: *Daily MIDI* — Maqam Nahawand in Bb (95 BPM)\n"
        "_A restless Tuesday in a bureaucracy that runs on reverb_\n"
        "\n"
        ":musical_keyboard: Melody — ImprovRNN, Flute (MIDI 73), temperature 1.2\n"
        ":drum_with_drumsticks: Drums — DrumsRNN, temperature 1.2\n"
        ":guitar: Bass — Programmatic from chord roots\n"
        ":musical_score: Chords — Bbm  Ebm7  Ab7  Dbmaj7"
    )
    result = parse_midi_message(text)
    assert result["scale"] == "Maqam Nahawand"
    assert result["root"] == "Bb"
    assert result["tempo"] == 95
    assert result["description"] == "A restless Tuesday in a bureaucracy that runs on reverb"
    assert result["chords"] == ["Bbm", "Ebm7", "Ab7", "Dbmaj7"]
    assert result["melody_instrument"] == 73
    assert result["temperature"] == 1.2


def test_parse_midi_message_returns_none_for_non_midi():
    """Non-Daily-MIDI messages return None."""
    assert parse_midi_message("just a random message") is None
    assert parse_midi_message(":wave: hello everyone") is None
```

**Step 2: Run tests to verify they fail**

Run: `cd puke-box && python -m pytest tests/test_scraper.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_midi_message'`

**Step 3: Implement message parser**

```python
# puke-box/scrape_midieval.py (initial — just the parser)
"""Scrape #midieval Slack channel and archive MIDI bot output."""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PUKE_BOX_DIR = Path(__file__).parent
MANIFEST_PATH = PUKE_BOX_DIR / "manifest.json"


def parse_midi_message(text: str) -> dict | None:
    """Parse a Daily MIDI message into structured metadata. Returns None if not a match."""
    # Match the header line: :musical_note: *Daily MIDI* — Scale in Root (Tempo BPM)
    header = re.search(
        r'\*Daily MIDI\*\s*—\s*(.+?)\s+in\s+(\w[#b]?)\s+\((\d+)\s*BPM\)', text
    )
    if not header:
        return None

    scale, root, tempo = header.group(1), header.group(2), int(header.group(3))

    # Description: italic text on second line
    desc_match = re.search(r'_(.+?)_', text)
    description = desc_match.group(1) if desc_match else ""

    # Chords: after ":musical_score: Chords —"
    chords_match = re.search(r':musical_score: Chords\s*—\s*(.+)', text)
    chords = chords_match.group(1).split() if chords_match else []

    # Melody instrument: "MIDI XX"
    melody_match = re.search(r'Melody.*?MIDI\s+(\d+)', text)
    melody_instrument = int(melody_match.group(1)) if melody_match else 0

    # Temperature
    temp_match = re.search(r'temperature\s+([\d.]+)', text)
    temperature = float(temp_match.group(1)) if temp_match else 1.0

    # Chord instrument: not in the message, default to 0
    chord_instrument = 0

    return {
        "scale": scale,
        "root": root,
        "tempo": tempo,
        "description": description,
        "chords": chords,
        "melody_instrument": melody_instrument,
        "chord_instrument": chord_instrument,
        "temperature": temperature,
    }
```

Also create `puke-box/tests/__init__.py` (empty) and add `sys.path` in the test or use `conftest.py`:

```python
# puke-box/tests/conftest.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

**Step 4: Run tests to verify they pass**

Run: `cd puke-box && python -m pytest tests/test_scraper.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add puke-box/scrape_midieval.py puke-box/tests/
git commit -m "feat(puke-box): add Slack message parser for #midieval"
```

---

### Task 2: Scraper — Slack API integration and file downloads

**Files:**
- Modify: `puke-box/scrape_midieval.py`

Add Slack API functions: find channel, fetch messages, fetch thread files, download MIDI files. Follow the drawma scraper's `_download_with_auth()` pattern for file downloads (manually follow redirects to preserve auth header).

**Step 1: Add Slack API functions**

Add to `scrape_midieval.py`:

```python
import os
from datetime import datetime, timezone, timedelta
import requests
from slack_sdk import WebClient

CHANNEL_NAME = "midieval"
MIDI_FILENAMES = {"melody.mid", "drums.mid", "bass.mid", "chords.mid"}


def _download_with_auth(url: str, token: str, timeout: int = 30) -> bytes:
    """Download file from Slack, manually following redirects to preserve auth."""
    headers = {"Authorization": f"Bearer {token}"}
    max_redirects = 5
    for _ in range(max_redirects):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()
        return resp.content
    raise RuntimeError(f"Too many redirects for {url}")


def find_channel_id(client: WebClient) -> str:
    """Find the #midieval channel ID."""
    cursor = None
    while True:
        resp = client.conversations_list(
            types="public_channel", limit=200, cursor=cursor
        )
        for ch in resp["channels"]:
            if ch["name"] == CHANNEL_NAME:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"Channel #{CHANNEL_NAME} not found")


def fetch_midi_messages(client: WebClient, channel_id: str) -> list[dict]:
    """Fetch all Daily MIDI messages from channel history."""
    messages = []
    cursor = None
    while True:
        resp = client.conversations_history(
            channel=channel_id, limit=200, cursor=cursor
        )
        for msg in resp["messages"]:
            parsed = parse_midi_message(msg.get("text", ""))
            if parsed:
                ts = float(msg["ts"])
                date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                parsed["date"] = date
                parsed["thread_ts"] = msg["ts"]
                messages.append(parsed)
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return messages


def download_thread_midi_files(
    client: WebClient, channel_id: str, thread_ts: str, output_dir: Path, token: str
) -> list[str]:
    """Download MIDI files from a thread's file uploads. Returns list of downloaded filenames."""
    resp = client.conversations_replies(
        channel=channel_id, ts=thread_ts, limit=100
    )
    downloaded = []
    for msg in resp["messages"]:
        for f in msg.get("files", []):
            name = f.get("name", "")
            if name in MIDI_FILENAMES:
                url = f.get("url_private_download") or f.get("url_private")
                if not url:
                    continue
                data = _download_with_auth(url, token)
                (output_dir / name).write_bytes(data)
                downloaded.append(name)
                logger.info(f"Downloaded {name}")
    return downloaded
```

**Step 2: Test manually with a dry-run print** (skip automated test — Slack API needs real credentials)

**Step 3: Commit**

```bash
git add puke-box/scrape_midieval.py
git commit -m "feat(puke-box): add Slack API integration and file downloads"
```

---

### Task 3: Scraper — OGG synthesis and manifest generation

**Files:**
- Modify: `puke-box/scrape_midieval.py`
- Create: `puke-box/tests/test_synthesis.py`

After downloading MIDIs, synthesize preview WAV using midi-bot's synthesizer, convert to OGG with ffmpeg, and generate/update the manifest.

**Step 1: Write failing test for manifest generation**

```python
# puke-box/tests/test_synthesis.py
import json
from pathlib import Path
from scrape_midieval import build_manifest


def test_build_manifest(tmp_path):
    """Build manifest from date directories."""
    # Create fake date dirs with meta.json
    for date, desc in [("2026-02-11", "Desc A"), ("2026-02-10", "Desc B")]:
        d = tmp_path / date
        d.mkdir()
        meta = {"scale": "Test", "root": "C", "tempo": 120, "description": desc}
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "preview.ogg").write_bytes(b"fake")

    manifest = build_manifest(tmp_path)
    assert len(manifest) == 2
    assert manifest[0]["date"] == "2026-02-11"  # newest first
    assert manifest[1]["date"] == "2026-02-10"
    assert manifest[0]["description"] == "Desc A"
```

**Step 2: Run test to verify it fails**

Run: `cd puke-box && python -m pytest tests/test_synthesis.py -v`
Expected: FAIL

**Step 3: Implement OGG synthesis and manifest**

Add to `scrape_midieval.py`:

```python
import importlib.util
import subprocess


def _import_synthesizer():
    """Import synthesize_preview from midi-bot's synthesizer module."""
    synth_path = Path(__file__).parent.parent / "midi-bot" / "src" / "synthesizer.py"
    spec = importlib.util.spec_from_file_location("synthesizer", synth_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.synthesize_preview


def synthesize_ogg(midi_dir: Path) -> bool:
    """Synthesize MIDI files to preview.ogg via WAV intermediate."""
    synthesize_preview = _import_synthesizer()
    wav_path = midi_dir / "preview.wav"
    ogg_path = midi_dir / "preview.ogg"

    if not synthesize_preview(midi_dir, wav_path):
        logger.error(f"Failed to synthesize WAV for {midi_dir}")
        return False

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "64k", str(ogg_path)],
            capture_output=True, check=True, timeout=30,
        )
        wav_path.unlink()  # clean up intermediate WAV
        logger.info(f"Synthesized {ogg_path}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"ffmpeg failed: {e}")
        return False


def build_manifest(puke_box_dir: Path) -> list[dict]:
    """Build manifest.json from all date directories."""
    entries = []
    for d in sorted(puke_box_dir.iterdir(), reverse=True):
        if not d.is_dir() or not (d / "meta.json").exists():
            continue
        meta = json.loads((d / "meta.json").read_text())
        entries.append({
            "date": d.name,
            "description": meta.get("description", ""),
            "scale": meta.get("scale", ""),
            "root": meta.get("root", ""),
            "tempo": meta.get("tempo", 0),
        })
    return entries
```

**Step 4: Run tests to verify they pass**

Run: `cd puke-box && python -m pytest tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add puke-box/scrape_midieval.py puke-box/tests/test_synthesis.py
git commit -m "feat(puke-box): add OGG synthesis and manifest generation"
```

---

### Task 4: Scraper — Main orchestrator

**Files:**
- Modify: `puke-box/scrape_midieval.py`

Wire everything together: fetch messages, skip existing dates, download MIDIs, synthesize OGG, write meta.json, update manifest.

**Step 1: Add main function**

```python
def get_existing_dates(puke_box_dir: Path) -> set[str]:
    """Get set of dates already archived."""
    return {
        d.name for d in puke_box_dir.iterdir()
        if d.is_dir() and (d / "preview.ogg").exists()
    }


def run_scraper() -> int:
    """Main scraper logic. Returns exit code."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        logger.error("SLACK_BOT_TOKEN not set")
        return 1

    client = WebClient(token=token)

    # Find channel
    channel_id = find_channel_id(client)
    logger.info(f"Found #{CHANNEL_NAME}: {channel_id}")

    # Fetch all Daily MIDI messages
    messages = fetch_midi_messages(client, channel_id)
    logger.info(f"Found {len(messages)} Daily MIDI messages")

    # Filter out already-archived dates
    existing = get_existing_dates(PUKE_BOX_DIR)
    new_messages = [m for m in messages if m["date"] not in existing]
    logger.info(f"{len(new_messages)} new entries to archive")

    if not new_messages:
        return 0

    for msg in new_messages:
        date_dir = PUKE_BOX_DIR / msg["date"]
        date_dir.mkdir(exist_ok=True)

        # Download MIDI files
        downloaded = download_thread_midi_files(
            client, channel_id, msg["thread_ts"], date_dir, token
        )
        if len(downloaded) < 4:
            logger.warning(f"{msg['date']}: only got {len(downloaded)}/4 MIDI files")

        # Synthesize OGG preview
        if not synthesize_ogg(date_dir):
            logger.warning(f"{msg['date']}: OGG synthesis failed, skipping")
            continue

        # Write meta.json
        meta = {k: v for k, v in msg.items() if k not in ("thread_ts",)}
        (date_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        logger.info(f"Archived {msg['date']}")

    # Rebuild manifest
    manifest = build_manifest(PUKE_BOX_DIR)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info(f"Manifest updated: {len(manifest)} entries")

    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    exit(run_scraper())
```

**Step 2: Commit**

```bash
git add puke-box/scrape_midieval.py
git commit -m "feat(puke-box): add main scraper orchestrator"
```

---

### Task 5: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/puke-box.yml`

**Step 1: Create workflow**

```yaml
# .github/workflows/puke-box.yml
name: Puke Box Archiver

on:
  schedule:
    - cron: '0 22 * * *'  # Daily at 10pm UTC (2 hours after midi bot's 8pm)
  workflow_dispatch:

jobs:
  archive:
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
        run: pip install slack-sdk requests pretty_midi scipy numpy

      - name: Scrape and archive
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        run: python puke-box/scrape_midieval.py

      - name: Commit new entries
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add puke-box/
          if git diff --cached --quiet; then
            echo "No new entries to commit."
          else
            git commit -m "chore: archive midieval entries ($(date -u +%Y-%m-%d)) [skip ci]"
            git push
          fi
```

**Step 2: Commit**

```bash
git add .github/workflows/puke-box.yml
git commit -m "feat(puke-box): add GitHub Actions workflow"
```

---

### Task 6: HTML page — structure, jukebox image, and geocities chaos

**Files:**
- Create: `puke-box.html`

Build the page shell: the jukebox image container with overlay zones, geocities chaos elements (tiled background, cursor trails, blinking text, marquees, visitor counter), and the basic CSS layout. No JavaScript interactivity yet — just the visual foundation.

**Step 1: Create the page**

The jukebox image (`img/puke-box.jpg`) is 338×600 pixels. Scale it up to fill most of the viewport. Position three overlay zones using percentage-based coordinates relative to the image container:

- **Marquee zone**: top ~18-28% of the image (the amber display)
- **Flipper zone**: middle ~38-68% (the lattice grid)
- **Controls zone**: bottom ~72-85% (the small display panel)

Include:
- Tiled background (CSS repeating pattern or a small tile image)
- `<marquee>` tags around the jukebox with jukebox-themed nonsense
- Cursor trail script (simple JS that spawns fading dots on mousemove)
- Blinking text elements ("NOW PLAYING", "HOT TRACKS", etc.) using CSS animation
- Comic Sans / system font stack
- Neon color clashes (green, hot pink, cyan, yellow)
- Fake visitor counter at page bottom
- Responsive: image + overlays scale together using a percentage-based container

Write the full HTML file with all CSS inline in `<style>` and the cursor trail in `<script>`. The three overlay zones should be empty `<div>`s with IDs (`#marquee-zone`, `#flipper-zone`, `#controls-zone`) ready for Task 7 to populate.

**Step 2: Test locally**

Open `puke-box.html` in browser. Verify:
- Jukebox image centered and large
- Three overlay zones visible (give them a temporary semi-transparent background)
- Cursor trails work
- Blinking text animates
- Marquees scroll
- Tiled background visible

**Step 3: Commit**

```bash
git add puke-box.html
git commit -m "feat(puke-box): add page shell with jukebox image and geocities chaos"
```

---

### Task 7: HTML page — flipper, audio player, and downloads

**Files:**
- Modify: `puke-box.html`

Add all JavaScript: fetch manifest, render the card flipper, audio playback, download links, and hash-based deep linking. This is the core interactivity.

**Step 1: Implement JavaScript**

Add a `<script>` block at the end of the page with:

**Manifest loading:**
```javascript
let manifest = [];
let currentIndex = 0;
let audio = new Audio();

async function loadManifest() {
    const resp = await fetch('puke-box/manifest.json');
    manifest = await resp.json();
    // Check URL hash for deep link
    const hash = location.hash.slice(1);
    if (hash) {
        const idx = manifest.findIndex(e => e.date === hash);
        if (idx >= 0) currentIndex = idx;
    }
    renderCard();
    loadTrack(currentIndex);
}
```

**Card flipper:**
```javascript
function renderCard() {
    const entry = manifest[currentIndex];
    // Format date retro style: "FEB•11•2026"
    // Show scale + root + tempo
    // Show description teaser (~50 chars)
    // Update the flipper zone innerHTML
}

function flipUp() {
    currentIndex = (currentIndex - 1 + manifest.length) % manifest.length;
    renderCard();
    loadTrack(currentIndex);
}

function flipDown() {
    currentIndex = (currentIndex + 1) % manifest.length;
    renderCard();
    loadTrack(currentIndex);
}
```

**Audio player:**
```javascript
async function loadTrack(index) {
    const entry = manifest[index];
    audio.src = `puke-box/${entry.date}/preview.ogg`;
    location.hash = entry.date;
    // Update marquee with full description
    // Update controls zone with track info
    audio.play().catch(() => {}); // ignore autoplay block
}
```

**Downloads:**
```javascript
function downloadMidi(track) {
    const entry = manifest[currentIndex];
    const a = document.createElement('a');
    a.href = `puke-box/${entry.date}/${track}.mid`;
    a.download = `${entry.date}-${track}.mid`;
    a.click();
}
```

**Keyboard navigation:**
```javascript
document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') flipUp();
    if (e.key === 'ArrowDown') flipDown();
    if (e.key === ' ') { audio.paused ? audio.play() : audio.pause(); e.preventDefault(); }
});
```

**Step 2: Test locally**

Create a test manifest and fake data directory:
```bash
mkdir -p puke-box/2026-02-11
echo '[{"date":"2026-02-11","description":"Test track","scale":"Test","root":"C","tempo":120}]' > puke-box/manifest.json
echo '{}' > puke-box/2026-02-11/meta.json
cp /tmp/miditest/preview.ogg puke-box/2026-02-11/preview.ogg
```

Open `puke-box.html` in browser. Verify:
- Card renders with date, scale, description
- Audio plays (may need to click play due to autoplay policy)
- Up/down arrows flip through cards
- URL hash updates
- Marquee scrolls the description

**Step 3: Commit**

```bash
git add puke-box.html
git commit -m "feat(puke-box): add flipper, audio player, and download functionality"
```

---

### Task 8: Homepage link

**Files:**
- Modify: `index.html`

Add a draggable thumbnail linking to puke-box.html on the homepage.

**Step 1: Read index.html and find where other page links are added**

Look for the drawma-icon or herstory patterns. Add a similar draggable element:

```html
<div class="draggable" data-id="pukebox" data-rotation="5"
     style="left: 55%; top: 80%; transform: rotate(5deg);">
    <a href="puke-box.html"><img src="img/puke-box.jpg" width="80"></a>
</div>
```

**Step 2: Test locally**

Open `index.html`, verify the puke-box thumbnail appears and is draggable. Click it to verify it links to `puke-box.html`.

**Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add puke-box link to homepage"
```

---

### Task 9: Run scraper, seed initial data, and end-to-end test

**Step 1: Run the scraper manually via GitHub Actions**

```bash
gh workflow run puke-box.yml
```

Watch the run, verify it succeeds, and check that `puke-box/manifest.json` and date directories are committed.

**Step 2: Pull the committed data and test the page**

```bash
git pull
```

Open `puke-box.html` in browser. Verify:
- Manifest loads, entries appear in flipper
- Audio plays for each track
- Downloads work
- Hash deep linking works
- Geocities chaos is present and unhinged

**Step 3: Commit any fixes**

---

### Task 10: Update design doc and MEMORY.md

**Files:**
- Modify: `docs/plans/2026-02-11-puke-box-design.md` — note any deviations from the plan
- Modify: MEMORY.md — add puke-box section with key conventions

**Commit:**
```bash
git commit -m "docs: update puke-box design doc and memory with final implementation notes"
```

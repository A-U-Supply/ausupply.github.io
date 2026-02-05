# History Time Machine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a VCR-styled time-travel page that lets visitors browse historical versions of the site via build-time snapshots.

**Architecture:** A shell script generates per-day snapshots of the site into `history/<date>-<hash>/` subdirectories with path rewriting (images point back to site root). `history.html` loads snapshots in an iframe with retro VCR transport controls. The script also archives pages to the Wayback Machine.

**Tech Stack:** Bash (snapshot generation), vanilla HTML/CSS/JS (history page), Internet Archive Save API (archiving)

---

### Task 1: Create the snapshot generation script

**Files:**
- Create: `scripts/generate-history.sh`

**Step 1: Create the scripts directory and script file**

```bash
#!/usr/bin/env bash
set -euo pipefail

# History snapshot generator for ausupply.github.io
# Generates static copies of the site at meaningful historical commits
# into history/<YYYY-MM-DD>-<short-hash>/ subdirectories.
#
# Usage: ./scripts/generate-history.sh [--archive]
#   --archive: Also archive pages to the Wayback Machine

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HISTORY_DIR="$REPO_ROOT/history"
MANIFEST="$HISTORY_DIR/manifest.json"
SITE_URL="https://ausupply.github.io"
DO_ARCHIVE=false

if [[ "${1:-}" == "--archive" ]]; then
    DO_ARCHIVE=true
fi

mkdir -p "$HISTORY_DIR"

# Directories/files to EXCLUDE from snapshots (not visual site content)
EXCLUDE_PATTERNS=(
    "docs/"
    "node_modules/"
    ".git/"
    ".github/"
    "scripts/"
    "history/"
    ".worktrees/"
    ".claude/"
    "README.md"
    "package.json"
    "CNAME"
    ".gitignore"
    "slack-song-generator/"
    "surreal-prompt-bot/"
)

# Build rsync exclude args
RSYNC_EXCLUDES=()
for pat in "${EXCLUDE_PATTERNS[@]}"; do
    RSYNC_EXCLUDES+=(--exclude "$pat")
done

# Get unique days that had visual file changes, with the last commit hash for each day
# Format: YYYY-MM-DD <short-hash> <full-hash> <commit-message>
echo "Scanning git history for meaningful commits..."

declare -a SNAPSHOTS=()

while IFS=$'\t' read -r date short_hash full_hash message; do
    snapshot_dir="$HISTORY_DIR/${date}-${short_hash}"

    # Skip if snapshot already exists (idempotent)
    if [[ -d "$snapshot_dir" ]]; then
        echo "  SKIP (exists): $date $short_hash - $message"
        SNAPSHOTS+=("$date|$short_hash|$full_hash|$message|$snapshot_dir")
        continue
    fi

    echo "  GENERATING: $date $short_hash - $message"

    # Check out the repo at this commit into a temp dir
    tmp_dir=$(mktemp -d)
    git -C "$REPO_ROOT" archive "$full_hash" | tar -x -C "$tmp_dir"

    # Copy site files, excluding non-site content
    mkdir -p "$snapshot_dir"
    rsync -a "${RSYNC_EXCLUDES[@]}" "$tmp_dir/" "$snapshot_dir/"

    # Rewrite image paths in HTML files so they point back to site root
    # From history/<date>-<hash>/page.html, img/foo.png -> ../../img/foo.png
    # Also handle CSimages/ references
    find "$snapshot_dir" -name '*.html' -exec sed -i '' \
        -e 's|src="img/|src="../../img/|g' \
        -e 's|src="CSimages/|src="../../CSimages/|g' \
        -e "s|src='img/|src='../../img/|g" \
        -e "s|src='CSimages/|src='../../CSimages/|g" \
        -e 's|url("img/|url("../../img/|g' \
        -e 's|url("fonts/|url("../../fonts/|g' \
        -e 's|href="vcfmw.css"|href="../../vcfmw.css"|g' \
        -e "s|href='vcfmw.css'|href='../../vcfmw.css'|g" \
        {} +

    # Strip <script> tags from HTML to prevent localStorage collisions
    # and show pages in their default layout
    find "$snapshot_dir" -name '*.html' -exec sed -i '' \
        -e '/<script>/,/<\/script>/d' \
        {} +

    # Clean up temp dir
    rm -rf "$tmp_dir"

    SNAPSHOTS+=("$date|$short_hash|$full_hash|$message|$snapshot_dir")
done < <(
    git -C "$REPO_ROOT" log --format="%ad%x09%h%x09%H%x09%s" --date=short \
        --diff-filter=AMCR -- '*.html' '*.css' '*.js' 'img/*' 'CSimages/*' \
    | awk -F'\t' '!seen[$1]++' \
    | sort -t$'\t' -k1,1
)

# Generate manifest.json
echo "Generating manifest.json..."
echo "[" > "$MANIFEST"
first=true
for entry in "${SNAPSHOTS[@]}"; do
    IFS='|' read -r date short_hash full_hash message snapshot_dir <<< "$entry"
    relative_path="history/${date}-${short_hash}/"

    if [ "$first" = true ]; then
        first=false
    else
        echo "," >> "$MANIFEST"
    fi

    # Escape double quotes in commit message for JSON
    escaped_message=$(echo "$message" | sed 's/"/\\"/g')

    printf '  {"hash":"%s","date":"%s","message":"%s","path":"%s"}' \
        "$short_hash" "$date" "$escaped_message" "$relative_path" >> "$MANIFEST"
done
echo "" >> "$MANIFEST"
echo "]" >> "$MANIFEST"

echo "Generated manifest with ${#SNAPSHOTS[@]} snapshots."

# Wayback Machine archiving
if [ "$DO_ARCHIVE" = true ]; then
    echo ""
    echo "Archiving pages to the Wayback Machine..."
    for html_file in "$REPO_ROOT"/*.html; do
        filename=$(basename "$html_file")
        url="${SITE_URL}/${filename}"
        echo "  Archiving: $url"
        curl -s -o /dev/null -w "  -> HTTP %{http_code}\n" \
            "https://web.archive.org/save/$url" || echo "  -> FAILED (will retry next run)"
        # Be polite — wait between requests
        sleep 2
    done
    echo "Wayback Machine archiving complete."
fi

echo ""
echo "Done! ${#SNAPSHOTS[@]} snapshots in $HISTORY_DIR"
```

Make it executable:
```bash
chmod +x scripts/generate-history.sh
```

**Step 2: Run the script and verify output**

Run: `./scripts/generate-history.sh`

Expected:
- `history/` directory created with ~76 subdirectories (one per day with visual changes)
- Each subdirectory contains HTML/CSS files with rewritten paths (no `img/` or `fonts/` directories within)
- `history/manifest.json` exists with entries for all snapshots
- No `<script>` tags in snapshot HTML files

Verify:
```bash
ls history/ | head -20
cat history/manifest.json | head -20
# Check an early snapshot for path rewriting
grep -c 'src="../../img/' history/$(ls history/ | head -1)/index.html
# Check script tags are stripped
grep -c '<script>' history/$(ls history/ | head -1)/index.html
```

**Step 3: Commit**

```bash
git add scripts/generate-history.sh
git commit -m "feat: add history snapshot generation script"
```

Note: Do NOT commit the `history/` directory yet — we'll do that after Task 2 so we can test the full flow.

---

### Task 2: Create history.html with VCR controls

**Files:**
- Create: `history.html`

**Step 1: Create the history page**

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TIME MACHINE — AUDIO UNITS SUPPLY</title>
    <link rel="stylesheet" href="vcfmw.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background-color: #1a1a1a;
            color: #ffbf00;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        header {
            flex-shrink: 0;
        }

        /* Viewport iframe */
        #viewport {
            flex: 1;
            border: none;
            width: 100%;
            background: #000;
        }

        /* VCR Control Bar */
        .vcr-bar {
            flex-shrink: 0;
            background: #2a2a2a;
            border-top: 3px solid #444;
            border-bottom: 3px solid #111;
            padding: 10px 15px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.5), 0 -1px 3px rgba(0,0,0,0.3);
        }

        /* Transport buttons */
        .vcr-btn {
            background: #333;
            border: 2px outset #555;
            color: #ffbf00;
            font-family: "3270Medium", monospace, Courier;
            font-size: 18px;
            padding: 8px 14px;
            cursor: pointer;
            min-width: 44px;
            text-align: center;
            user-select: none;
        }

        .vcr-btn:hover {
            background: #444;
            color: #ffd700;
        }

        .vcr-btn:active {
            border-style: inset;
            background: #222;
        }

        .vcr-btn.active {
            background: #553300;
            border-color: #ffbf00;
            text-shadow: 0 0 8px #ffbf00;
        }

        /* LED readout */
        .led-readout {
            flex: 1;
            font-family: "3270Medium", monospace, Courier;
            font-size: 16px;
            color: #ffbf00;
            text-shadow: 0 0 6px rgba(255, 191, 0, 0.6);
            background: #111;
            border: 2px inset #333;
            padding: 6px 12px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            min-width: 0;
        }

        .led-date {
            color: #ff6600;
            text-shadow: 0 0 6px rgba(255, 102, 0, 0.6);
        }

        /* Counter display */
        .counter {
            font-family: "3270Medium", monospace, Courier;
            font-size: 14px;
            color: #ffbf00;
            text-shadow: 0 0 4px rgba(255, 191, 0, 0.4);
            background: #111;
            border: 2px inset #333;
            padding: 6px 10px;
            white-space: nowrap;
        }

        /* Scrubber bar */
        .scrubber-container {
            width: 100%;
            padding: 4px 15px 8px;
            background: #2a2a2a;
        }

        .scrubber-track {
            width: 100%;
            height: 12px;
            background: #111;
            border: 1px inset #333;
            cursor: pointer;
            position: relative;
        }

        .scrubber-fill {
            height: 100%;
            background: #ffbf00;
            pointer-events: none;
            transition: width 0.2s ease;
        }

        .scrubber-ticks {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
        }

        .scrubber-tick {
            position: absolute;
            top: 0;
            width: 1px;
            height: 100%;
            background: rgba(255, 191, 0, 0.2);
        }

        /* Loading state */
        .loading .led-readout {
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        /* Mobile adjustments */
        @media (max-width: 600px) {
            .vcr-bar {
                flex-wrap: wrap;
                gap: 6px;
                padding: 8px 10px;
            }
            .vcr-btn {
                padding: 6px 10px;
                font-size: 16px;
            }
            .led-readout {
                font-size: 13px;
                order: 5;
                width: 100%;
            }
            .counter {
                font-size: 12px;
            }
        }
    </style>
</head>

<body class="loading">
<header>
    <a href="index.html"><img src="img/cheeze-bourger2.png" alt="Header Image"></a>
    <h1>TIME MACHINE</h1>
</header>

<iframe id="viewport" src="about:blank"></iframe>

<div class="scrubber-container">
    <div class="scrubber-track" id="scrubber">
        <div class="scrubber-fill" id="scrubberFill"></div>
        <div class="scrubber-ticks" id="scrubberTicks"></div>
    </div>
</div>

<div class="vcr-bar">
    <button class="vcr-btn" id="btnRewind" title="Previous">&#9664;&#9664;</button>
    <button class="vcr-btn" id="btnPlay" title="Play">&#9654;</button>
    <button class="vcr-btn" id="btnStop" title="Stop">&#9632;</button>
    <button class="vcr-btn" id="btnFastFwd" title="Next">&#9654;&#9654;</button>
    <div class="led-readout" id="ledReadout">LOADING...</div>
    <div class="counter" id="counter">--/--</div>
</div>

<script>
    let manifest = [];
    let currentIndex = 0;
    let playInterval = null;
    const PLAY_SPEED_MS = 3500;

    const viewport = document.getElementById('viewport');
    const ledReadout = document.getElementById('ledReadout');
    const counter = document.getElementById('counter');
    const scrubberFill = document.getElementById('scrubberFill');
    const scrubberTicks = document.getElementById('scrubberTicks');
    const scrubber = document.getElementById('scrubber');
    const btnPlay = document.getElementById('btnPlay');
    const btnStop = document.getElementById('btnStop');
    const btnRewind = document.getElementById('btnRewind');
    const btnFastFwd = document.getElementById('btnFastFwd');

    function loadSnapshot(index) {
        if (index < 0 || index >= manifest.length) return;
        currentIndex = index;
        const snap = manifest[index];
        viewport.src = snap.path + 'index.html';
        ledReadout.innerHTML = '<span class="led-date">' + snap.date + '</span> ' + snap.message;
        counter.textContent = (index + 1) + '/' + manifest.length;
        updateScrubber();
    }

    function updateScrubber() {
        const pct = manifest.length > 1
            ? (currentIndex / (manifest.length - 1)) * 100
            : 100;
        scrubberFill.style.width = pct + '%';
    }

    function buildTicks() {
        scrubberTicks.innerHTML = '';
        if (manifest.length <= 1) return;
        manifest.forEach(function(_, i) {
            const tick = document.createElement('div');
            tick.className = 'scrubber-tick';
            tick.style.left = (i / (manifest.length - 1)) * 100 + '%';
            scrubberTicks.appendChild(tick);
        });
    }

    function startPlay() {
        if (playInterval) return;
        btnPlay.classList.add('active');
        playInterval = setInterval(function() {
            if (currentIndex < manifest.length - 1) {
                loadSnapshot(currentIndex + 1);
            } else {
                stopPlay();
            }
        }, PLAY_SPEED_MS);
    }

    function stopPlay() {
        if (playInterval) {
            clearInterval(playInterval);
            playInterval = null;
        }
        btnPlay.classList.remove('active');
    }

    // Button handlers
    btnRewind.addEventListener('click', function() {
        stopPlay();
        if (currentIndex > 0) loadSnapshot(currentIndex - 1);
    });

    btnFastFwd.addEventListener('click', function() {
        stopPlay();
        if (currentIndex < manifest.length - 1) loadSnapshot(currentIndex + 1);
    });

    btnPlay.addEventListener('click', function() {
        if (playInterval) {
            stopPlay();
        } else {
            startPlay();
        }
    });

    btnStop.addEventListener('click', function() {
        stopPlay();
    });

    // Scrubber click
    scrubber.addEventListener('click', function(e) {
        stopPlay();
        const rect = scrubber.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        const index = Math.round(pct * (manifest.length - 1));
        loadSnapshot(Math.max(0, Math.min(manifest.length - 1, index)));
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            stopPlay();
            if (currentIndex > 0) loadSnapshot(currentIndex - 1);
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            stopPlay();
            if (currentIndex < manifest.length - 1) loadSnapshot(currentIndex + 1);
        } else if (e.key === ' ') {
            e.preventDefault();
            if (playInterval) stopPlay();
            else startPlay();
        }
    });

    // Load manifest and start
    fetch('history/manifest.json')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            manifest = data;
            document.body.classList.remove('loading');
            buildTicks();
            loadSnapshot(0);
        })
        .catch(function(err) {
            ledReadout.textContent = 'ERROR: Could not load history manifest';
            console.error('Failed to load manifest:', err);
        });
</script>
</body>
</html>
```

**Step 2: Verify the page loads**

Open `history.html` in a browser. It should show:
- The shared header
- A black iframe area
- The scrubber bar
- VCR buttons with amber text on dark background
- An error in the LED readout if manifest doesn't exist yet (expected)

Note: The manifest won't load via `file://` due to CORS — you'll need to serve it locally or test after deploying. To test locally:
```bash
cd /Users/jake/au-supply/ausupply.github.io && python3 -m http.server 8000
```
Then visit `http://localhost:8000/history.html`

**Step 3: Commit**

```bash
git add history.html
git commit -m "feat: add history time machine page with VCR controls"
```

---

### Task 3: Generate snapshots and test the full flow

**Step 1: Run the generation script**

```bash
./scripts/generate-history.sh
```

Verify:
- Check number of snapshot directories: `ls -d history/*-*/ | wc -l` (expect ~76)
- Check manifest: `cat history/manifest.json | python3 -m json.tool | head -30`
- Check path rewriting in a snapshot: `grep 'src="../../img/' history/$(ls -d history/*-*/ | head -1 | xargs basename)/index.html | head -3`
- Check no script tags: `grep '<script>' history/$(ls -d history/*-*/ | head -1 | xargs basename)/index.html | wc -l` (expect 0)

**Step 2: Test in browser**

```bash
cd /Users/jake/au-supply/ausupply.github.io && python3 -m http.server 8000
```

Visit `http://localhost:8000/history.html` and verify:
- First snapshot loads in the iframe
- Rewind/forward buttons navigate between snapshots
- Play button auto-advances
- Stop button halts playback
- Scrubber bar is clickable and shows position
- LED readout shows date and commit message
- Counter shows current/total
- Arrow keys navigate, spacebar toggles play
- Images load correctly in snapshots (via `../../img/` path)

**Step 3: Check snapshot sizes**

```bash
du -sh history/
du -sh history/ --exclude='*.png' --exclude='*.jpg' --exclude='*.gif' --exclude='*.webp' 2>/dev/null
```

The total should be reasonable (mostly HTML/CSS, no image duplication).

**Step 4: Commit snapshots**

```bash
git add history/
git commit -m "feat: generate initial history snapshots"
```

---

### Task 4: Add homepage link to the time machine

**Files:**
- Modify: `index.html`

**Step 1: Add a draggable "Time Machine" element to index.html**

Add a new draggable element before the `<footer>` tag:

```html
<div class="draggable" data-id="timemachine" data-rotation="3"
     style="left: 70%; top: 10%; transform: rotate(3deg);">
    <div class="continue-link">
        <a href="history.html">&#9194; Time Machine</a>
    </div>
</div>
```

This uses the existing `.continue-link` style (Comic Sans, dotted border, yellow background) for the geocities look. The ⏪ emoji (&#9194;) adds the rewind icon.

**Step 2: Verify in browser**

Open `index.html` — the "Time Machine" link should appear as a draggable element. Clicking it should navigate to `history.html`.

**Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add time machine link to homepage"
```

---

### Task 5: Add history/ to .gitignore considerations and update docs

**Step 1: Update the design doc status**

In `docs/plans/2026-02-05-history-time-machine-design.md`, change the status from "Approved" to "Implemented".

**Step 2: Update MEMORY.md**

Add a section about the history time machine to the project memory:

```markdown
## History Time Machine
- `history.html` — VCR-styled time-travel page, loads historical snapshots in iframe
- `scripts/generate-history.sh` — generates snapshots from git history into `history/<date>-<hash>/`
- Snapshots contain HTML/CSS only — image paths rewritten to `../../img/` to avoid duplication
- `<script>` tags stripped from snapshots to prevent localStorage collisions
- `history/manifest.json` — snapshot metadata consumed by the page
- Run with `--archive` flag to also save pages to the Wayback Machine
- One snapshot per day (last qualifying commit), ~76 snapshots currently
```

**Step 3: Commit**

```bash
git add docs/plans/2026-02-05-history-time-machine-design.md
git add /Users/jake/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md
git commit -m "docs: update design doc and memory with implementation details"
```

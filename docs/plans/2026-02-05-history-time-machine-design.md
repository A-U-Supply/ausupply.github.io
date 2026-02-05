# History Time Machine — Design Doc

**Date:** 2026-02-05
**Status:** Implemented

## Overview

A VCR-styled time-travel feature that lets visitors browse the full site as it existed at different points in its git history. Lives on a dedicated `history.html` page, linked from the homepage.

## Architecture

### Approach: Build-time Subdirectory Snapshots

A shell script generates static copies of the site at meaningful historical commits into `history/<date>-<short-hash>/` subdirectories. A manifest file lists all available snapshots. `history.html` loads snapshots into an iframe with VCR transport controls.

If repo size becomes a concern, this can be swapped to a GitHub API + client-side approach — only the snapshot loading function changes; the UI stays the same.

## Snapshot Generation

**Script:** `scripts/generate-history.sh`

1. Walks git commit history
2. Filters to commits that changed visual files (`.html`, `.css`, `.js`, `img/*`)
3. Skips commits that only touch `docs/`, `README.md`, `package.json`, `scripts/`, `history/`
4. For each qualifying commit, checks out the repo and copies site files into `history/<YYYY-MM-DD>-<short-hash>/`
5. Excludes non-site files: `docs/`, `node_modules/`, `.git/`, `scripts/`, `history/`
6. Strips localStorage JavaScript from snapshots so they show default/original layout
7. Generates `history/manifest.json`

**Manifest format:**
```json
[
  {
    "hash": "abc1234",
    "date": "2025-06-15",
    "message": "feat: make homepage content draggable",
    "path": "history/2025-06-15-abc1234/"
  }
]
```

The script is idempotent — re-running skips existing snapshots and only adds new ones.

### Wayback Machine Archiving

After generating local snapshots, the same script archives the live site's pages to the Internet Archive via their "Save Page Now" API (`https://web.archive.org/save/<url>`). It loops through all `.html` files in the site root and submits each one (e.g., `https://web.archive.org/save/https://ausupply.github.io/index.html`). This provides an independent off-site backup of each version alongside the local snapshots.

## history.html Page

### Layout

- **Top:** Shared header (cheeze-bourger2.png + h1, per site convention)
- **Middle:** Iframe viewport filling available space, displaying the selected snapshot
- **Bottom:** VCR control bar, fixed to bottom

### VCR Control Bar

Styled like a physical VCR transport panel:

- **Dark enclosure** — dark gray/black bar with beveled border
- **Transport buttons** — chunky, rectangular, embossed. Amber text on dark background
  - ◀◀ Rewind — previous snapshot
  - ▶ Play — auto-advance chronologically (one snapshot every 3-4 seconds)
  - ▶▶ Fast-forward — next snapshot
  - ■ Stop — pause auto-play
- **LED readout** — date and commit message in 3270Medium amber with subtle glow
- **Scrubber bar** — horizontal track with draggable playhead, amber fill for played portion, tick marks per snapshot

### Behavior

- On page load, fetches `history/manifest.json`
- Default view: earliest snapshot (rewound to the beginning)
- Play mode advances one snapshot every 3-4 seconds
- All navigation within a snapshot happens inside the iframe
- No scrollbar on outer page — scrolling is within the iframe

## Visual Design

- Matches site aesthetic: `vcfmw.css`, 3270Medium font, amber color scheme
- VCR bar: dark panel with beveled edges, chunky retro buttons
- LED readout: monospace amber text with glow effect
- Minimal page — header, viewport, controls. Historical content is the star.

## Homepage Link

A draggable element on the homepage links to `history.html` (e.g., "⏪ Time Machine" or "Rewind").

## Edge Cases

- **Relative paths:** Site already uses relative paths everywhere, so snapshot internal links just work within the iframe
- **localStorage collisions:** Snapshots share the same origin. Solved by stripping localStorage JS from snapshot copies so they always show default layout.
- **No recursive nesting:** Generation script excludes `history/` when copying
- **Repo size:** Estimated 30-50 snapshots at 2-5MB each = ~60-250MB worst case. Manageable, monitor over time. Escape hatch: switch to GitHub API approach (Approach B).

## Future Possibilities (not in v1)

- Speed control for auto-play
- GitHub Action to auto-generate snapshots on push
- Switch to GitHub API approach if repo size grows too large

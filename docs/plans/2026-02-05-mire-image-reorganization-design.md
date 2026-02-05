# Mire Image Reorganization

## Goal

Move all mire.html images into a dedicated `img/mire/` subdirectory. Update the GitHub Action to only optimize images in `img/mire/`, and auto-add new images to mire.html.

## File Reorganization

Move 14 image pairs (PNG + WebP) from `img/` to `img/mire/`:

- 07-15
- 07-22 Page 1, 07-22 Page 2
- CH28-29 draw1, ch28-29
- latex1
- ubk copy
- Ch27-drawing
- CRG-drawing5
- Ch25-section3, CH25-section4
- CRG drawing 1, CRG-Drawing 2

Update all `/img/` references in `mire.html` to `/img/mire/`.

## GitHub Action

Updated `optimize-images.yml`:

- **Trigger**: `img/mire/**.png` only (no longer processes root `img/`)
- **Convert**: `cwebp -q 80` scoped to `img/mire/`
- **Auto-update HTML**: detect new WebP files not already in `mire.html`, then:
  - Insert a date heading (`<h1>Month Day, Year</h1>`) at the top of `<body>`
  - Add `<a><img></a><br>` blocks per new image (75% width, lazy loading)
  - `<a>` links to PNG original, `<img>` shows WebP
  - Multiple images from the same push grouped under one heading
  - New images ordered alphabetically within the group
- **Commit**: both new WebPs and updated `mire.html`

## Edge Cases

- No new PNGs in push: skip HTML update
- Re-pushed PNG (same filename): regenerate WebP, don't duplicate HTML entry
- Filenames with spaces: handled with proper quoting

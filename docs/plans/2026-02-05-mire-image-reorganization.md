# Mire Image Reorganization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move all mire.html images into `img/mire/`, update references, and rewrite the GitHub Action to only optimize `img/mire/` images and auto-add new ones to mire.html.

**Architecture:** Three sequential tasks — file moves via git, HTML path updates, and a rewritten GitHub Action workflow. No dependencies or build tools beyond git and the existing cwebp in CI.

**Tech Stack:** HTML, GitHub Actions (YAML), bash (shell scripting in CI)

---

### Task 1: Create `img/mire/` and move images

**Files:**
- Create directory: `img/mire/`
- Move from `img/` to `img/mire/`: 14 PNG+WebP pairs (28 files total)

**Step 1: Create the subdirectory and move all mire images**

Run:
```bash
cd /Users/jake/au-supply/ausupply.github.io
mkdir -p img/mire
git mv "img/07-15.png" "img/07-15.webp" img/mire/
git mv "img/07-22 Page 1.png" "img/07-22 Page 1.webp" img/mire/
git mv "img/07-22 Page 2.png" "img/07-22 Page 2.webp" img/mire/
git mv "img/CH28-29 draw1.png" "img/CH28-29 draw1.webp" img/mire/
git mv "img/ch28-29.png" "img/ch28-29.webp" img/mire/
git mv "img/latex1.png" "img/latex1.webp" img/mire/
git mv "img/ubk copy.png" "img/ubk copy.webp" img/mire/
git mv "img/Ch27-drawing.png" "img/Ch27-drawing.webp" img/mire/
git mv "img/CRG-drawing5.png" "img/CRG-drawing5.webp" img/mire/
git mv "img/Ch25-section3.png" "img/Ch25-section3.webp" img/mire/
git mv "img/CH25-section4.png" "img/CH25-section4.webp" img/mire/
git mv "img/CRG drawing 1.png" "img/CRG drawing 1.webp" img/mire/
git mv "img/CRG-Drawing 2.png" "img/CRG-Drawing 2.webp" img/mire/
```

**Step 2: Verify all 28 files are in `img/mire/`**

Run:
```bash
ls img/mire/ | wc -l
```
Expected: `28`

**Step 3: Commit**

```bash
git add -A img/
git commit -m "refactor: move mire images to img/mire/"
```

---

### Task 2: Update mire.html image paths

**Files:**
- Modify: `mire.html` (all `/img/` references become `/img/mire/`)

**Step 1: Replace all `/img/` paths with `/img/mire/` in mire.html**

Use find-and-replace to change every `href="/img/` to `href="/img/mire/` and every `src="/img/` to `src="/img/mire/` in `mire.html`. There are 14 `href` and 14 `src` references to update (28 total).

The YouTube link on line 58 (`href="https://..."`) must NOT be touched — only `/img/` paths.

**Step 2: Verify no bare `/img/` paths remain (except non-image links)**

Run:
```bash
grep -c '"/img/' mire.html
```
Expected: `0` (all references now point to `/img/mire/`)

**Step 3: Spot-check the HTML structure is intact**

Read `mire.html` and verify:
- All `<a href="/img/mire/...png">` links are correct
- All `<img src="/img/mire/...webp">` sources are correct
- The YouTube link on line 58 is unchanged

**Step 4: Commit**

```bash
git add mire.html
git commit -m "refactor: update mire.html image paths to /img/mire/"
```

---

### Task 3: Rewrite the GitHub Action

**Files:**
- Modify: `.github/workflows/optimize-images.yml`

**Step 1: Replace the entire workflow file with the new version**

Write this content to `.github/workflows/optimize-images.yml`:

```yaml
name: Optimize Mire Images

on:
  push:
    branches: [master]
    paths:
      - 'img/mire/**.png'

  workflow_dispatch:

jobs:
  optimize:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Install webp tools
        run: sudo apt-get update && sudo apt-get install -y webp

      - name: Convert new PNGs to WebP
        run: |
          converted=0
          new_images=""
          for png in img/mire/*.png; do
            [ -f "$png" ] || continue
            webp="${png%.png}.webp"
            if [ ! -f "$webp" ] || [ "$png" -nt "$webp" ]; then
              echo "Converting: $png -> $webp"
              cwebp -q 80 "$png" -o "$webp"
              converted=$((converted + 1))
              # Track basename (without extension) for HTML update
              basename="$(basename "$png" .png)"
              # Check if this image is already referenced in mire.html
              if ! grep -qF "/img/mire/${basename}.webp" mire.html; then
                new_images="${new_images}${basename}"$'\n'
              fi
            fi
          done
          echo "Converted $converted file(s)"
          echo "CONVERTED=$converted" >> "$GITHUB_ENV"
          # Write new image list to temp file for next step
          printf '%s' "$new_images" > /tmp/new_images.txt

      - name: Update mire.html with new images
        if: env.CONVERTED != '0'
        run: |
          # Read new images list
          new_images="$(cat /tmp/new_images.txt)"
          [ -z "$new_images" ] && echo "No new images to add to HTML" && exit 0

          echo "Adding new images to mire.html:"
          echo "$new_images"

          # Build the HTML block for all new images
          today="$(date +'%B %-d, %Y')"
          block="<h1>${today}</h1>"$'\n'

          while IFS= read -r name; do
            [ -z "$name" ] && continue
            block="${block}<a href=\"/img/mire/${name}.png\">"$'\n'
            block="${block}\t<img src=\"/img/mire/${name}.webp\" alt=\"\" width=\"75%\" loading=\"lazy\">"$'\n'
            block="${block}</a>"$'\n'
            block="${block}<br>"$'\n'
          done <<< "$new_images"

          block="${block}<br>"

          # Insert after <body> tag
          sed -i "s|<body>|<body>\n${block}|" mire.html

          echo "HTML_UPDATED=1" >> "$GITHUB_ENV"

      - name: Commit changes
        if: env.CONVERTED != '0'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add img/mire/*.webp mire.html
          git commit -m "chore: optimize mire images and update HTML [skip ci]"
          git push
```

**Step 2: Review the workflow logic**

Verify:
- Trigger path is `img/mire/**.png`
- Conversion loop scoped to `img/mire/*.png`
- New image detection checks `mire.html` for existing references before adding
- HTML insertion happens after `<body>` tag
- Images grouped under one date heading
- Filenames with spaces handled (all variables quoted)
- Commit includes both `img/mire/*.webp` and `mire.html`

**Step 3: Commit**

```bash
git add .github/workflows/optimize-images.yml
git commit -m "feat: rewrite image action for img/mire/ with auto HTML update"
```

---

### Task 4: Final verification

**Step 1: Verify git status is clean**

```bash
git status
```
Expected: clean working tree

**Step 2: Verify file structure**

```bash
ls img/mire/*.png | wc -l
ls img/mire/*.webp | wc -l
```
Expected: 14 PNGs, 14 WebPs

**Step 3: Verify mire.html has no stale `/img/` references**

```bash
grep '"/img/' mire.html | grep -v '/img/mire/'
```
Expected: no output (all paths point to `/img/mire/`)

**Step 4: Review the 3 commits**

```bash
git log --oneline -3
```
Expected:
```
feat: rewrite image action for img/mire/ with auto HTML update
refactor: update mire.html image paths to /img/mire/
refactor: move mire images to img/mire/
```

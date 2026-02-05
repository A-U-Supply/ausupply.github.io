# mire.html Image Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make mire.html load fast by converting PNGs to WebP, adding lazy loading, linking to originals, and automating future conversions via GitHub Actions.

**Architecture:** A GitHub Action watches for new/changed PNGs in `img/`, converts them to WebP, and commits the WebP files back. mire.html serves the lightweight WebP versions with lazy loading, and each image links to the original PNG. A README documents the workflow.

**Tech Stack:** GitHub Actions, cwebp (libwebp), HTML

---

### Task 1: Update mire.html with WebP sources, lazy loading, and original links

**Files:**
- Modify: `mire.html:1-54`

**Step 1: Rewrite mire.html**

Replace the entire file with the updated version. Every `<img>` becomes a lazy-loaded WebP wrapped in a link to the original PNG. Add a viewport meta tag and minimal CSS to remove link borders.

```html
<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>CRG Drawings</title>
	<style>
		a img { border: none; }
	</style>
</head>
<body>
<h1>July 22, 2025 [Chapter 32-33]</h1>
<a href="/img/07-22 Page 1.png">
	<img src="/img/07-22 Page 1.webp" alt="" width="50%" loading="lazy">
</a>
<br>
<a href="/img/07-22 Page 2.png">
	<img src="/img/07-22 Page 2.webp" alt="" width="50%" loading="lazy">
</a>
<br>
<br>
<h1>July 15, 2025 [Chapter 30-31]</h1>
<a href="/img/07-15.png">
	<img src="/img/07-15.webp" alt="" width="50%" loading="lazy">
</a>
<br>
<br>
<h1>July 1, 2025 [Chapter 28-29]</h1>
<a href="/img/CH28-29 draw1.png">
	<img src="/img/CH28-29 draw1.webp" alt="" width="50%" loading="lazy">
</a>
<br>
<a href="/img/ch28-29.png">
	<img src="/img/ch28-29.webp" alt="" width="50%" loading="lazy">
</a>
<br>
<br>
<h1>June 24, 2025 [Chapter 27]</h1>
<a href="/img/latex1.png">
	<img src="/img/latex1.webp" alt="" width="50%" loading="lazy">
</a>
<br>
<a href="/img/ubk copy.png">
	<img src="/img/ubk copy.webp" alt="" width="75%" loading="lazy">
</a>
<br>
<br>
<a href="/img/Ch27-drawing.png">
	<img src="/img/Ch27-drawing.webp" alt="" width="75%" loading="lazy">
</a>
<br>
<br>
<h1>June 10, 2025 [Chapter 26]</h1>
<a href="/img/CRG-drawing5.png">
	<img src="/img/CRG-drawing5.webp" alt="" width="75%" loading="lazy">
</a>
<br>
	<a href="https://www.youtube.com/watch?v=7Do9dMUiaM8&t=61s">
clip3 "I'm your king!" -Monty Python and the Holy Grail (1975)</a>
<br>
<br>
 <h1>June 3, 2025 [Chapter 25, Section 3 & 4]</h1>
<a href="/img/Ch25-section3.png">
	<img src="/img/Ch25-section3.webp" alt="" width="75%" loading="lazy">
</a>
<br>
<a href="/img/CH25-section4.png">
	<img src="/img/CH25-section4.webp" alt="" width="75%" loading="lazy">
</a>
<br>
<br>
  <h1>May 13, 2025 [Chapter 25, Section 1]</h1>
<a href="/img/CRG drawing 1.png">
	<img src="/img/CRG drawing 1.webp" alt="" width="75%" loading="lazy">
</a>
<br>
<a href="/img/CRG-Drawing 2.png">
	<img src="/img/CRG-Drawing 2.webp" alt="" width="75%" loading="lazy">
</a>


</body>
</html>
```

**Step 2: Verify the HTML is valid**

Visually inspect: every `<img>` should have `loading="lazy"`, a `.webp` src, and be wrapped in an `<a>` linking to the `.png` original.

**Step 3: Commit**

```bash
git add mire.html
git commit -m "feat: optimize mire.html with WebP sources, lazy loading, and links to originals"
```

---

### Task 2: Create the GitHub Actions workflow

**Files:**
- Create: `.github/workflows/optimize-images.yml`

**Step 1: Create the workflow file**

```yaml
name: Convert PNGs to WebP

on:
  push:
    branches: [master]
    paths:
      - 'img/**.png'

  workflow_dispatch:

jobs:
  convert:
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
          for png in img/*.png; do
            [ -f "$png" ] || continue
            webp="${png%.png}.webp"
            if [ ! -f "$webp" ] || [ "$png" -nt "$webp" ]; then
              echo "Converting: $png -> $webp"
              cwebp -q 80 "$png" -o "$webp"
              converted=$((converted + 1))
            else
              echo "Skipping (up to date): $png"
            fi
          done
          echo "Converted $converted file(s)"
          echo "CONVERTED=$converted" >> "$GITHUB_ENV"

      - name: Commit WebP files
        if: env.CONVERTED != '0'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add img/*.webp
          git commit -m "chore: auto-convert PNGs to WebP [skip ci]"
          git push
```

Key details:
- Triggers on push to master when any `img/*.png` changes, or manually via workflow_dispatch
- Only converts PNGs that don't have a WebP yet, or where the PNG is newer
- `[skip ci]` in commit message prevents infinite loop
- `workflow_dispatch` lets you trigger it manually for the initial batch conversion
- Quality 80 is a good balance for drawings (visually identical, much smaller)

**Step 2: Verify the YAML is valid**

Check indentation is correct (YAML is whitespace-sensitive).

**Step 3: Commit**

```bash
git add .github/workflows/optimize-images.yml
git commit -m "feat: add GitHub Action to auto-convert PNGs to WebP"
```

---

### Task 3: Run initial WebP conversion locally

The GitHub Action will handle future images, but we need WebP files for the existing images right now. We'll convert them locally and commit.

**Step 1: Check if cwebp is installed**

```bash
which cwebp || brew install webp
```

**Step 2: Convert all PNGs referenced by mire.html**

```bash
cd img/
for png in \
  "07-22 Page 1.png" \
  "07-22 Page 2.png" \
  "07-15.png" \
  "CH28-29 draw1.png" \
  "ch28-29.png" \
  "latex1.png" \
  "ubk copy.png" \
  "Ch27-drawing.png" \
  "CRG-drawing5.png" \
  "Ch25-section3.png" \
  "CH25-section4.png" \
  "CRG drawing 1.png" \
  "CRG-Drawing 2.png"; do
  webp="${png%.png}.webp"
  echo "Converting: $png -> $webp"
  cwebp -q 80 "$png" -o "$webp"
done
```

**Step 3: Verify sizes improved**

```bash
ls -lh img/*.webp
```

Expect each WebP to be significantly smaller than the original PNG.

**Step 4: Commit**

```bash
git add img/*.webp
git commit -m "chore: add initial WebP versions of mire.html images"
```

---

### Task 4: Create README.md

**Files:**
- Create: `README.md` (repo root)

**Step 1: Write the README**

```markdown
# ausupply.github.io

Audio Units Supply website. Deliberately chaotic, geocities-inspired.

## Image Optimization

Large PNG images (especially on `mire.html`) are automatically converted to WebP for faster loading.

### How it works

1. Push PNG images to `img/`
2. A GitHub Action automatically converts them to WebP (quality 80)
3. The WebP versions are committed back to the repo
4. HTML pages serve the WebP versions with `loading="lazy"`
5. Each image links to the original full-size PNG

### Adding new images to mire.html

1. Add your PNG to `img/`
2. Push to master - the Action converts it to WebP automatically
3. Add the image to `mire.html` using this pattern:

```html
<a href="/img/your-image.png">
	<img src="/img/your-image.webp" alt="" width="75%" loading="lazy">
</a>
```

### Manual conversion

If you need to convert locally (e.g. before pushing):

```bash
# Install webp tools (macOS)
brew install webp

# Convert a single image
cwebp -q 80 img/your-image.png -o img/your-image.webp
```

### Triggering the Action manually

Go to Actions > "Convert PNGs to WebP" > Run workflow. This converts all PNGs that don't have WebP versions yet.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with image optimization workflow"
```

---

### Task 5: Update docs

**Files:**
- Modify: `docs/AUDIO-UNITS-SUPPLY-WEB-TOOLS.md`

**Step 1: Add image optimization section**

After the "File Locations" section (line 163), add:

```markdown
## Image Optimization

PNG images are automatically converted to WebP via GitHub Actions for faster page loads.

- **Trigger:** Push a PNG to `img/` on master
- **Action:** `.github/workflows/optimize-images.yml` converts to WebP (quality 80)
- **HTML pattern:** `<a href="original.png"><img src="optimized.webp" loading="lazy"></a>`
- **Manual trigger:** Actions > "Convert PNGs to WebP" > Run workflow

See `README.md` for full details.
```

**Step 2: Commit**

```bash
git add docs/AUDIO-UNITS-SUPPLY-WEB-TOOLS.md
git commit -m "docs: add image optimization info to web tools guide"
```

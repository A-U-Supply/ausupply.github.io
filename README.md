# ausupply.github.io

Audio Units Supply website. Deliberately chaotic, geocities-inspired.

## Interactive Homepage

All content on `index.html` (YouTube embed, images, links) is draggable with full mouse and touch support:

- **Mouse**: click and drag to move, scroll wheel to rotate
- **Touch**: single finger drag, pinch to resize, two-finger twist to rotate
- **Keyboard**: arrow left/right to rotate, arrow up/down to resize (select an item first)
- Positions persist in localStorage across visits

## Shared Header

All pages use a shared header defined in `vcfmw.css` with the standard structure:

```html
<header>
    <a href="index.html"><img src="img/cheeze-bourger2.png" alt="Header Image"></a>
    <h1>AUDIO UNITS SUPPLY</h1>
</header>
```

The header image links to the homepage. Use the same image across pages unless a page needs something different.

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

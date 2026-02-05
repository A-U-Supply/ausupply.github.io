# Shared Header Design

## Goal

Move the `<h1>AUDIO UNITS SUPPLY</h1>` from the `.content` div into the `<header>` element on index.html, and make the header a shared, reusable component across all pages via `vcfmw.css`.

## Header Structure

Every page uses:

```html
<header>
    <a href="index.html"><img src="img/cheeze-bourger2.png" alt="Header Image"></a>
    <h1>AUDIO UNITS SUPPLY</h1>
</header>
```

- Image links to homepage
- Same image across all pages unless otherwise noted
- Pages can omit the image if needed

## CSS

Shared styles added to `vcfmw.css`:

- `header` — yellow `#ffcc00` background, centered text, red bottom border
- `header img` — full-width, black border, drop shadow
- `header h1` — red Courier New, text-shadow, scoped to header so other h1s unaffected

Styles moved from index.html's inline `<style>` to avoid duplication.

## Changes

1. **`vcfmw.css`** — Added `header`, `header img`, `header h1` rules
2. **`index.html`** — Links `vcfmw.css`, moved h1 into header, wrapped image in homepage link, removed redundant inline header/h1 styles

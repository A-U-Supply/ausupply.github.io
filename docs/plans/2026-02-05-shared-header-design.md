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

- Image links to homepage via relative path (`index.html`, not `/`)
- Same image across all pages unless otherwise noted
- Pages can omit the image if needed

## CSS

Shared styles in `vcfmw.css`:

- `header` — transparent background (inherits page body), centered text, red bottom border
- `header img` — full-width, black border, drop shadow
- `header h1` — red Courier New, text-shadow, scoped to `header h1` so other h1s unaffected

## Pages Updated

1. **`index.html`** — Links `vcfmw.css`, moved h1 into header, wrapped image in homepage link, removed redundant inline header/h1 styles
2. **`this-song-is-a-junkyard.html`** — Links `vcfmw.css`, added shared header above existing page header

## Touch Support (this-song-is-a-junkyard.html)

Added full touch interaction for the draggable song title elements:

- **Single finger** — drag titles
- **Pinch** — resize titles (font-size, clamped 8px-120px)
- **Two-finger twist** — rotate titles
- Seamless transition between drag and pinch gestures
- `touch-action: none` on `.title` prevents browser default gestures
- SIZE +/- toolbar buttons for mouse and touch resize
- Arrow up/down keyboard shortcuts for resize
- Font-size saved/loaded in localStorage

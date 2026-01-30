# Audio Units Supply - Web Tools & Pages

A guide to our website tools and ideas for new chaotic web art. Use this doc with `/superpowers:brainstorm` to cook up new pages and features.

---

## What We Have

### The Website: ausupply.github.io

A deliberately chaotic, geocities-inspired website. Pages are scattered, weird, and fun. Current pages:

- **index.html** - Main landing with embedded videos and images
- **songtitles.html** - Static chaos page of song titles
- **this-song-is-a-junkyard.html** - Interactive song title collage (drag, rotate, colorize)
- Various other experimental pages (mire.html, audex pages, etc.)

### The Song Title Generator Tool

Location: `slack-song-generator/`

**What it does:**
1. Pulls messages from our `#song-titles` Slack channel
2. Uses a local AI (Ollama) to filter out discussion and keep only actual title ideas
3. Generates a chaotic HTML page with titles scattered everywhere

**Key features:**
- Randomized positions, rotations, colors, fonts
- Multiple color palettes: neon, pastel, mono
- Optional media (GIFs, images) scattered in
- Reproducible chaos with seed numbers
- Cached titles for quick regeneration

**Current interactive features (this-song-is-a-junkyard.html):**
- Drag titles anywhere
- Scroll wheel to rotate
- Click color buttons to change colors
- Animation effects: blink, pulse, rainbow, shake, float
- Saves your arrangement to browser storage

---

## How It Works (Non-Technical)

1. **Slack → Tool**: The tool reads our `#song-titles` channel
2. **AI Filter**: Ollama (local AI) decides what's a title vs. what's just chat
3. **Chaos Engine**: Randomly positions everything with different sizes/colors/angles
4. **HTML Output**: Spits out a single HTML file we push to the website
5. **Interactive Mode**: JavaScript lets viewers rearrange things

---

## Ideas for New Pages & Features

### New Data Sources

- **Lyrics channel** → Chaotic lyric collage page
- **Band photos** → Scattered photo gallery with weird effects
- **Show dates/venues** → Retro tour poster generator
- **Gear/samples list** → Equipment shrine page
- **Voice memos/recordings** → Audio player embedded in chaos

### New Visual Styles

- **Marquee madness** - Everything scrolls in different directions
- **ASCII art mode** - Convert titles to ASCII text art
- **VHS glitch aesthetic** - Tracking lines, color bleed, static
- **Windows 95 theme** - Dialog boxes, error messages, desktop icons
- **Fridge magnets** - Titles look like magnet letters on a fridge
- **Ransom note** - Cut-out newspaper letters style
- **Neon signs** - Glowing text on dark background
- **Chalkboard** - Handwritten style on green/black board

### New Interactive Features

- **Collision physics** - Titles bounce off each other
- **Sound on hover** - Each title plays a sound/note
- **Typing mode** - Titles appear as if being typed
- **Gravity mode** - Titles fall and pile up at bottom
- **Magnet mode** - Titles attract/repel from cursor
- **Drawing mode** - Users can draw on the page
- **Sticker mode** - Drag from a sticker sheet onto canvas
- **Export as image** - Save your arrangement as PNG

### New Page Types

- **Random title picker** - Spin wheel / slot machine for picking titles
- **Title generator** - Combine random words from our titles
- **Title voting** - Band members vote on favorites
- **Timeline** - When each title was suggested
- **Word cloud** - Most common words in titles
- **Title-a-day** - Shows one random title, changes daily

### Multi-Page Ideas

- **Album art generator** - Arrange titles into album cover layouts
- **Setlist builder** - Drag titles into a setlist order
- **Zine generator** - Auto-layout titles into printable zine pages

---

## Technical Capabilities

Things the current tool can do that we could expand on:

- **Pull from any Slack channel** (just change the channel ID)
- **Filter with custom prompts** (could classify by mood, theme, etc.)
- **Multiple templates** (could have different .j2 files for different styles)
- **Media integration** (already supports scattering images/GIFs)
- **Seed-based reproducibility** (same seed = same layout)
- **Caching** (regenerate quickly without hitting Slack again)

---

## Example Brainstorm Prompts

Use these with `/superpowers:brainstorm`:

> "I want to create a new page that shows our song titles as a Windows 95 desktop with each title as a file icon"

> "Can we make a page where the titles fall from the top and pile up, and you can shake the page to scatter them?"

> "I want to pull from our #gear channel and make a shrine page for our equipment with photos and descriptions"

> "Let's make a ransom-note style page where titles look like cut-out magazine letters"

> "Can we add sound - each title plays a little synth note when you hover over it?"

---

## Running the Tool

For whoever has Claude Code set up:

```bash
cd slack-song-generator

# Fetch fresh titles from Slack
uv run ./generate-song-page.py --fetch-only

# Generate a new page with random chaos
uv run ./generate-song-page.py --generate-only --random --output ../new-page.html

# Generate with specific settings
uv run ./generate-song-page.py --generate-only --color-palette neon --max-rotation 45 --output ../new-page.html
```

---

## File Locations

```
ausupply.github.io/
├── index.html                    # Main page
├── songtitles.html              # Static song title chaos
├── this-song-is-a-junkyard.html # Interactive version
├── img/                         # Images and GIFs
├── slack-song-generator/        # The generator tool
│   ├── src/templates/           # HTML templates (edit these for new styles)
│   └── cache/titles.json        # Cached song titles
└── docs/
    └── AUDIO-UNITS-SUPPLY-WEB-TOOLS.md  # This file
```

---

## Contributing Ideas

Don't use Claude Code? No problem:

1. Drop ideas in Slack
2. Share this doc with someone who does have it set up
3. They can run `/superpowers:brainstorm` with your idea
4. Review the design together
5. Build it!

---

*Last updated: 2026-01-30*

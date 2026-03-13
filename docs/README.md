# docs/ Index

## Top-Level

- [AUDIO-UNITS-SUPPLY-WEB-TOOLS.md](AUDIO-UNITS-SUPPLY-WEB-TOOLS.md) — Overview of the site's tools and capabilities: song title generator, interactive pages, and brainstorming prompts for new features.
- [how-to-edit-this-site.md](how-to-edit-this-site.md) — Non-technical walkthrough for editing the site using GitHub Desktop (cloning, branching, editing HTML, previewing, committing, PRs).

## plans/

### Site Infrastructure

- [2026-02-05-shared-header-design.md](plans/2026-02-05-shared-header-design.md) — Unified header component (cheeze-bourger2.png + h1) shared across pages via vcfmw.css, with draggable content and touch support on index.html.

### Song Title Integration

Song titles from #song-titles Slack channel used as creative seeds across the generation pipeline. A new `song-titles-bot/` scrapes and filters titles via HF Inference API, stores them with metadata, and regenerates the interactive `this-song-is-a-junkyard.html` page. The midi-bot uses titles as the primary LLM prompt seed (replacing headlines), and glottisdale-bot uses them for deterministic seeding and labeling.

- [2026-03-13-song-title-integration-design.md](plans/2026-03-13-song-title-integration-design.md) — Design: song-titles-bot scraper, midi-bot prompt rework, glottisdale-bot seeding, hymnal-bot parser tweak, scheduling.
- [2026-01-30-slack-song-title-generator-design.md](plans/2026-01-30-slack-song-title-generator-design.md) — (Superseded) Original design: Slack fetcher, Ollama LLM filter, chaotic HTML generator.
- [2026-01-30-slack-song-generator-implementation.md](plans/2026-01-30-slack-song-generator-implementation.md) — (Superseded) Original implementation plan.

### Surreal Prompt Bot (#drawma)

Daily bot that posts surrealist drawing prompts to Slack. Scrapes news headlines from 8 sources, mixes them with artistic inspirations (movements, techniques, artists), and feeds the mix to Groq's Llama API to generate a prompt.

- [2026-01-30-surreal-prompt-bot-design.md](plans/2026-01-30-surreal-prompt-bot-design.md) — Design: headline scraping, inspiration sampling, Groq LLM generation, Slack posting.
- [2026-01-30-surreal-prompt-bot-implementation.md](plans/2026-01-30-surreal-prompt-bot-implementation.md) — Implementation plan (10 tasks).

### Mire Image Gallery

- [2026-02-05-mire-image-optimization.md](plans/2026-02-05-mire-image-optimization.md) — PNG-to-WebP conversion, lazy loading, linking originals, automated GH Actions conversion at quality-80.
- [2026-02-05-mire-image-reorganization-design.md](plans/2026-02-05-mire-image-reorganization-design.md) — Moving mire images into `img/mire/` subdirectory and rewriting the GH Action to auto-update mire.html with dated headings.
- [2026-02-05-mire-image-reorganization.md](plans/2026-02-05-mire-image-reorganization.md) — Short overview of the image reorg: directory move, HTML reference updates, GH Action rewrite.

### History Time Machine

VCR-styled time-travel page that loads historical snapshots of the site in an iframe. A shell script generates snapshots from git history (one per day), stripping scripts and rewriting image paths to avoid duplication.

- [2026-02-05-history-time-machine-design.md](plans/2026-02-05-history-time-machine-design.md) — Design: snapshot generation from git, VCR transport controls (rewind/play/fast-forward/stop), optional Wayback Machine archiving.
- [2026-02-05-history-time-machine-implementation.md](plans/2026-02-05-history-time-machine-implementation.md) — Implementation plan (5 tasks).

### Drawma Gallery

Twin Peaks-themed dark gallery for surrealist drawings from the #drawma Slack channel. Features a strobing chevron background, gothic ornate frames, backwards-text animations, and "whispers" — prompt fragments that float across the screen.

A daily scraper pulls new images from Slack (with auth-preserving redirect handling and content-type validation), saves them with metadata to a manifest, and also scrapes the full channel history for prompt texts used by the whisper animations.

- [2026-02-05-drawma-gallery-design.md](plans/2026-02-05-drawma-gallery-design.md) — Design: gallery aesthetic, navigation, scraper architecture, whisper system, strobe toggle.
- [2026-02-05-drawma-gallery-implementation.md](plans/2026-02-05-drawma-gallery-implementation.md) — Implementation plan (8 tasks).

### Daily MIDI Bot (#midieval)

Daily bot that generates 4 MIDI tracks (melody, drums, bass, chords) and posts them to Slack. Pipeline: scrape news headlines → LLM generates musical parameters (scale, tempo, chords, instruments) → Magenta.js neural networks (ImprovRNN for melody, DrumsRNN for drums) + programmatic generation (bass, chords) → post to Slack.

Requires Node 18 (Magenta.js is incompatible with Node 20+). The LLM sometimes hallucinates invalid instruments or out-of-range tempos, so a validator auto-corrects bad params instead of crashing.

- [2026-02-06-daily-midi-bot-design.md](plans/2026-02-06-daily-midi-bot-design.md) — Design: headline scraping, LLM param generation, Magenta.js MIDI generation, Slack posting.
- [2026-02-06-daily-midi-bot-implementation.md](plans/2026-02-06-daily-midi-bot-implementation.md) — Implementation plan (13 tasks).

### Muzzik Playlist Bot (#muzzik)

Daily bot that scrapes YouTube links from the #muzzik Slack channel and adds them to an unlisted YouTube playlist. Tracks all URLs in a committed state file, classifies YouTube vs non-YouTube links, handles playlist rollover at 5,000 videos, and respects the YouTube API's daily quota (~190 inserts/day).

- [2026-02-11-muzzik-playlist-design.md](plans/2026-02-11-muzzik-playlist-design.md) — Design: URL extraction/classification, state tracking, OAuth2 refresh token flow, playlist management.
- [2026-02-11-muzzik-playlist-implementation.md](plans/2026-02-11-muzzik-playlist-implementation.md) — Implementation plan.

### Puke Box (MIDI Jukebox)

A 90s geocities-inspired jukebox web page for browsing daily MIDI bot output. A jukebox stock photo serves as the centerpiece with three interactive overlay zones: an amber marquee display, a card flipper showing track metadata, and an audio player with seek. Each day's entry has downloadable MIDI files and a synthesized OGG preview.

A scraper pulls posts from #midieval, downloads the MIDI files, synthesizes OGG previews using pretty_midi + scipy + ffmpeg, and organizes them into per-day directories with a manifest for the page to consume.

- [2026-02-11-puke-box-design.md](plans/2026-02-11-puke-box-design.md) — Design: jukebox UI, overlay zones, scraper/synthesizer, geocities aesthetic.
- [2026-02-11-puke-box-implementation.md](plans/2026-02-11-puke-box-implementation.md) — Implementation plan (10 tasks).

### Glottisdale (Syllable Audio Collage + Vocal MIDI Mapping)

Extracted to its own repository: **[A-U-Supply/glottisdale](https://github.com/A-U-Supply/glottisdale)**

Syllable-level audio collage tool and vocal MIDI mapping engine. The library (`pip install`) handles all audio processing; thin bot wrappers in this repo (`glottisdale-bot/`, `hymnal-bot/`) handle Slack I/O and Magenta.js MIDI extension.

Design docs moved to the glottisdale repo under `docs/legacy/`.

### AU Tmux Status Bar

Green terminal-themed tmux status bar for the `au` tmuxinator session. Full restyle (status bar, window tabs, pane borders, messages) with a rotating right-side display cycling through git branch, moon phase, session entropy plant, and anagram roulette.

- [2026-02-19-au-tmux-status-bar-design.md](plans/2026-02-19-au-tmux-status-bar-design.md) — Design: color scheme, layout, rotation script, status items.

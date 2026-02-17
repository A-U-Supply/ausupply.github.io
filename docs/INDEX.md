# docs/ Index

## Top-Level

- [AUDIO-UNITS-SUPPLY-WEB-TOOLS.md](AUDIO-UNITS-SUPPLY-WEB-TOOLS.md) — Overview of the site's tools and capabilities: song title generator, interactive pages, and brainstorming prompts for new features.
- [how-to-edit-this-site.md](how-to-edit-this-site.md) — Non-technical walkthrough for editing the site using GitHub Desktop (cloning, branching, editing HTML, previewing, committing, PRs).

## plans/

### Site Infrastructure

- [2026-02-05-shared-header-design.md](plans/2026-02-05-shared-header-design.md) — Unified header component (cheeze-bourger2.png + h1) shared across pages via vcfmw.css, with draggable content and touch support on index.html.

### Song Title Generator

- [2026-01-30-slack-song-title-generator-design.md](plans/2026-01-30-slack-song-title-generator-design.md) — Python CLI that fetches song titles from Slack, filters via local Ollama LLM, and generates chaotic geocities HTML with randomized positions/colors/fonts.
- [2026-01-30-slack-song-generator-implementation.md](plans/2026-01-30-slack-song-generator-implementation.md) — 10-task implementation plan: scaffolding, Slack fetcher, Ollama filter, chaos generator, Jinja2 template, cache, CLI, README, tests.

### Surreal Prompt Bot (#drawma)

- [2026-01-30-surreal-prompt-bot-design.md](plans/2026-01-30-surreal-prompt-bot-design.md) — Daily GitHub Actions bot that scrapes headlines, mixes with artistic inspirations, and generates surreal drawing prompts via Groq Llama API for Slack #drawma.
- [2026-01-30-surreal-prompt-bot-implementation.md](plans/2026-01-30-surreal-prompt-bot-implementation.md) — 10-task plan: scaffolding, config, 8-source news scraper, inspiration sampler, Groq generator, Slack poster, orchestrator, GH Actions, tests, docs.

### Mire Image Gallery

- [2026-02-05-mire-image-optimization.md](plans/2026-02-05-mire-image-optimization.md) — PNG-to-WebP conversion, lazy loading, linking originals, automated GH Actions conversion at quality-80.
- [2026-02-05-mire-image-reorganization-design.md](plans/2026-02-05-mire-image-reorganization-design.md) — Moving mire images into `img/mire/` subdirectory and rewriting the GH Action to auto-update mire.html with dated headings.
- [2026-02-05-mire-image-reorganization.md](plans/2026-02-05-mire-image-reorganization.md) — Short overview of the image reorg: directory move, HTML reference updates, GH Action rewrite.

### History Time Machine

- [2026-02-05-history-time-machine-design.md](plans/2026-02-05-history-time-machine-design.md) — VCR-styled time-travel page loading historical site snapshots in an iframe with retro transport controls (rewind, play, fast-forward, stop) and optional Wayback Machine archiving.
- [2026-02-05-history-time-machine-implementation.md](plans/2026-02-05-history-time-machine-implementation.md) — 5-task plan: snapshot generation script, history.html with VCR controls, initial snapshots, homepage link, docs.

### Drawma Gallery

- [2026-02-05-drawma-gallery-design.md](plans/2026-02-05-drawma-gallery-design.md) — Twin Peaks-themed dark gallery for #drawma surrealist drawings: strobing chevron background, gothic frames, whisper animations, daily Slack scraper.
- [2026-02-05-drawma-gallery-implementation.md](plans/2026-02-05-drawma-gallery-implementation.md) — 8-task plan: image directory, icon resize, scraper tests + implementation, gallery HTML/CSS/JS, homepage link, GH Actions, docs.

### Daily MIDI Bot (#midieval)

- [2026-02-06-daily-midi-bot-design.md](plans/2026-02-06-daily-midi-bot-design.md) — Daily MIDI generator: scrapes headlines, LLM generates music params (scale, chords, tempo, instruments), Magenta.js generates 4 tracks, posts to Slack #midieval.
- [2026-02-06-daily-midi-bot-implementation.md](plans/2026-02-06-daily-midi-bot-implementation.md) — 13-task plan: scaffolding, scales/instruments DBs, inspirations, config, LLM generator, Slack uploader, Node.js MIDI generator, orchestrator, GH Actions, tests.

### Muzzik Playlist Bot (#muzzik)

- [2026-02-11-muzzik-playlist-design.md](plans/2026-02-11-muzzik-playlist-design.md) — Slack scraper that maintains an unlisted YouTube playlist from #muzzik channel URLs, with state tracking, OAuth2 refresh token auth, and daily GH Action.
- [2026-02-11-muzzik-playlist-implementation.md](plans/2026-02-11-muzzik-playlist-implementation.md) — Step-by-step plan: URL extraction/classification, Slack scraper, state management, YouTube API client, orchestrator, GH Actions, tests.

### Puke Box (MIDI Jukebox)

- [2026-02-11-puke-box-design.md](plans/2026-02-11-puke-box-design.md) — 90s geocities jukebox page for daily MIDI output: stock photo with overlay zones (marquee, card flipper, audio player), MIDI downloads, cursor trails, blinking text.
- [2026-02-11-puke-box-implementation.md](plans/2026-02-11-puke-box-implementation.md) — 10-task plan: Slack parser, API integration, OGG synthesis, scraper orchestrator, GH Actions, HTML shell, JS flipper/player, homepage link, E2E tests, docs.

### Glottisdale (Syllable Audio Collage)

- [2026-02-15-glottisdale-design.md](plans/2026-02-15-glottisdale-design.md) — Syllable-level audio collage tool: Whisper ASR + g2p_en phonemes + vendored syllabifier, ffmpeg cut/concat, library-first design with optional Slack integration.
- [2026-02-15-glottisdale-implementation.md](plans/2026-02-15-glottisdale-implementation.md) — Core implementation plan: scaffolding, Whisper transcription, ARPABET conversion, syllabifier, audio cutting, concatenation, CLI, Slack integration.
- [2026-02-15-glottisdale-natural-speech-design.md](plans/2026-02-15-glottisdale-natural-speech-design.md) — Extension to make output sound like natural flowing speech via hierarchical prosodic phrasing (phrases → sentences) and phonotactic syllable ordering.
- [2026-02-15-glottisdale-natural-speech-implementation.md](plans/2026-02-15-glottisdale-natural-speech-implementation.md) — Plan for phonotactics module (junction scoring), prosodic hierarchy, and updated `process()` pipeline.
- [2026-02-15-glottisdale-audio-polish-design.md](plans/2026-02-15-glottisdale-audio-polish-design.md) — Audio quality improvements: pink noise bed, room tone extraction, pitch/volume normalization, breath insertion, prosodic dynamics, longer crossfades.
- [2026-02-15-glottisdale-audio-polish-implementation.md](plans/2026-02-15-glottisdale-audio-polish-implementation.md) — Plan for `analysis.py` module (numpy-based WAV I/O, RMS, F0, room tone, breaths), feature integration into `process()`, CLI flags.

### Hymnal Gargler (MIDI Vocal Collage)

- [2026-02-16-hymnal-gargler-design.md](plans/2026-02-16-hymnal-gargler-design.md) — Daily bot combining MIDI melodies with Glottisdale syllable collages to produce "drunk choir singing" via rubberband pitch/time shifting, vibrato, chorus, and loose melodic following.
- [2026-02-16-hymnal-gargler-implementation.md](plans/2026-02-16-hymnal-gargler-implementation.md) — Plan: scaffolding, MIDI parser, syllable prep, vocal mapper engine, Magenta.js extender, mixer, Slack fetcher/poster, CLI, GH Actions, tests.

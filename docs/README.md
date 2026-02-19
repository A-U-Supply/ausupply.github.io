# docs/ Index

## Top-Level

- [AUDIO-UNITS-SUPPLY-WEB-TOOLS.md](AUDIO-UNITS-SUPPLY-WEB-TOOLS.md) — Overview of the site's tools and capabilities: song title generator, interactive pages, and brainstorming prompts for new features.
- [how-to-edit-this-site.md](how-to-edit-this-site.md) — Non-technical walkthrough for editing the site using GitHub Desktop (cloning, branching, editing HTML, previewing, committing, PRs).

## plans/

### Site Infrastructure

- [2026-02-05-shared-header-design.md](plans/2026-02-05-shared-header-design.md) — Unified header component (cheeze-bourger2.png + h1) shared across pages via vcfmw.css, with draggable content and touch support on index.html.

### Song Title Generator

Generates the chaotic `this-song-is-a-junkyard.html` page. Pulls song titles from Slack, uses a local LLM to filter for the best ones, and renders them with randomized positions/colors/fonts in geocities style.

- [2026-01-30-slack-song-title-generator-design.md](plans/2026-01-30-slack-song-title-generator-design.md) — Design: Slack fetcher, Ollama LLM filter, chaotic HTML generator with Jinja2 templates.
- [2026-01-30-slack-song-generator-implementation.md](plans/2026-01-30-slack-song-generator-implementation.md) — Implementation plan (10 tasks).

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

### Glottisdale (Syllable Audio Collage)

Syllable-level audio collage tool. Takes speech audio, chops it into individual syllables using linguistic analysis (not duration-based), randomly shuffles them, and concatenates the result into an audio collage that sounds like someone speaking a language you don't understand.

**How syllable extraction works:** The pipeline uses NLP/linguistics, not raw audio analysis, to find syllable boundaries:

1. **Whisper ASR** transcribes speech to text with word-level timestamps (e.g. "hello" = 0.5s–0.9s)
2. **g2p_en** converts each word to ARPABET phonemes (e.g. "hello" → `HH AH0 L OW1`) — a linguistic phoneme representation
3. **Vendored syllabifier** (from kylebgorman/syllabify) splits phonemes into syllables using the **Maximum Onset Principle** — a real linguistics rule about how consonants cluster around vowel nuclei
4. **Proportional timing** maps syllable boundaries back to audio using Whisper's word timestamps — since Whisper only provides word-level (not phoneme-level) times, intra-word syllable cuts are estimated proportionally
5. **ffmpeg** cuts the audio at those boundaries, then pieces are shuffled and concatenated with crossfades

The main design doc also discusses the abstract aligner interface (`align.py`) retained for future forced-alignment integration, which would give per-phoneme timestamps instead of the proportional estimates in step 4.

- [2026-02-15-glottisdale-design.md](plans/2026-02-15-glottisdale-design.md) — **Start here.** Core design: full pipeline, package structure, Whisper → g2p_en → syllabifier → ffmpeg cut/concat, library-first architecture with optional Slack integration.
- [2026-02-15-glottisdale-implementation.md](plans/2026-02-15-glottisdale-implementation.md) — Core implementation plan.

**Natural speech extension:** Makes the output flow like natural speech instead of choppy isolated syllables. Adds hierarchical prosodic phrasing (syllables → words → phrases → sentence groups, each with appropriate pause lengths) and phonotactic ordering (scoring syllable junctions so transitions between clips sound like plausible speech).

- [2026-02-15-glottisdale-natural-speech-design.md](plans/2026-02-15-glottisdale-natural-speech-design.md) — Design: prosodic hierarchy, weighted syllable-per-word distribution, phonotactic junction scoring.
- [2026-02-15-glottisdale-natural-speech-implementation.md](plans/2026-02-15-glottisdale-natural-speech-implementation.md) — Implementation plan: phonotactics module, prosodic hierarchy, pipeline integration.

**Audio polish extension:** Addresses the "digital" quality of the output. Adds a subtle pink noise bed (eliminates the void between clips), room tone extraction (fills gaps with actual ambient sound from the source instead of digital silence), pitch normalization (smooths out wild pitch variation between syllables from different moments), volume normalization, breath insertion at phrase boundaries, and prosodic dynamics (phrase-onset boost, phrase-final softening). All features use numpy for analysis and ffmpeg for processing, all CLI-configurable with `--flag`/`--no-flag` toggles.

- [2026-02-15-glottisdale-audio-polish-design.md](plans/2026-02-15-glottisdale-audio-polish-design.md) — Design: pink noise, room tone, pitch/volume normalization, breath detection, prosodic dynamics.
- [2026-02-15-glottisdale-audio-polish-implementation.md](plans/2026-02-15-glottisdale-audio-polish-implementation.md) — Implementation plan: `analysis.py` module, feature integration, CLI flags.

### Hymnal Gargler (MIDI Vocal Collage)

Daily bot that combines Glottisdale syllable collages with Daily MIDI Bot melodies to produce "singing" — the aesthetic goal is **"drunk choir learns a melody"**. Takes syllable clips, normalizes their pitch to a common baseline using rubberband, then maps each syllable onto MIDI melody notes with intentional imperfections: gaussian pitch drift (±2 semitones), vibrato on held notes, chorus layering on long notes, and ±20% rhythmic jitter. The result is nonsensical vocal tracks that loosely follow the melody.

Pipeline: fetch MIDI from #midieval → extend via Magenta.js to ~40s → fetch speech videos from #sample-sale → Whisper transcribe → Glottisdale syllabify → normalize pitch/volume → map syllables to melody notes → render with rubberband → mix vocal + MIDI backing → post to #glottisdale.

- [2026-02-16-hymnal-gargler-design.md](plans/2026-02-16-hymnal-gargler-design.md) — Design: architecture, vocal mapping engine, pitch drift/vibrato/chorus, mixer, Slack integration.
- [2026-02-16-hymnal-gargler-implementation.md](plans/2026-02-16-hymnal-gargler-implementation.md) — Implementation plan: MIDI parser, syllable prep, vocal mapper, Magenta extender, mixer, Slack fetcher/poster, CLI, tests.

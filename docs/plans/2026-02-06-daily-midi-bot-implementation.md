# Daily MIDI Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a GitHub Actions bot that generates 4 MIDI files daily (melody, drums, bass, chords) using Magenta.js + programmatic code, driven by LLM-selected world scales, and posts them to Slack `#midieval`.

**Architecture:** Python orchestrator reuses the surreal-prompt-bot's scraper/sampler, calls Llama 3.3 70B for structured musical params (scale, chords, tempo, instruments), shells out to a Node.js script for MIDI generation (Magenta.js ImprovRNN + DrumsRNN for melody/drums, programmatic for bass/chords), then uploads 4 MIDI files to Slack.

**Tech Stack:** Python 3.11 (huggingface_hub, slack-sdk, pyyaml, requests, beautifulsoup4), Node.js 20 (@magenta/music, tonal, @tensorflow/tfjs-node)

**Design doc:** `docs/plans/2026-02-06-daily-midi-bot-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `midi-bot/package.json`
- Create: `midi-bot/requirements.txt`
- Create: `midi-bot/config.yaml`
- Create: `midi-bot/src/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p midi-bot/src
```

**Step 2: Create `package.json`**

```json
{
  "name": "midi-bot",
  "version": "1.0.0",
  "private": true,
  "description": "Daily MIDI generator using Magenta.js",
  "dependencies": {
    "@magenta/music": "^1.23.1",
    "@tensorflow/tfjs-node": "^4.22.0",
    "tonal": "^6.2.0"
  }
}
```

**Step 3: Create `requirements.txt`**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
huggingface_hub>=0.20.0
slack-sdk>=3.27.0
pyyaml>=6.0.0
pytest>=8.0.0
```

**Step 4: Create `config.yaml`**

```yaml
slack:
  channel: "#midieval"

prompt:
  temperature: 1.0
  model: meta-llama/Llama-3.3-70B-Instruct
  max_headlines: 10

inspirations:
  file: inspirations.txt
  pick_count: 2

sources:
  - reuters
  - foxnews
  - cnn
  - bbc
  - ft
  - npr
  - guardian
  - breitbart
```

**Step 5: Create empty `src/__init__.py`**

```python
```

**Step 6: Commit**

```bash
git add midi-bot/package.json midi-bot/requirements.txt midi-bot/config.yaml midi-bot/src/__init__.py
git commit -m "feat(midi-bot): scaffold project structure"
```

---

## Task 2: Scales Database

**Files:**
- Create: `midi-bot/scales.json`

**Step 1: Create `scales.json` with 60+ world scales**

Each entry has: `name` (string), `intervals` (array of semitones from root), `origin` (string).

```json
[
  {"name": "Major (Ionian)", "intervals": [0,2,4,5,7,9,11], "origin": "Western"},
  {"name": "Natural Minor (Aeolian)", "intervals": [0,2,3,5,7,8,10], "origin": "Western"},
  {"name": "Dorian", "intervals": [0,2,3,5,7,9,10], "origin": "Western/Medieval"},
  {"name": "Phrygian", "intervals": [0,1,3,5,7,8,10], "origin": "Western/Medieval"},
  {"name": "Lydian", "intervals": [0,2,4,6,7,9,11], "origin": "Western/Medieval"},
  {"name": "Mixolydian", "intervals": [0,2,4,5,7,9,10], "origin": "Western/Medieval"},
  {"name": "Locrian", "intervals": [0,1,3,5,6,8,10], "origin": "Western/Medieval"},
  {"name": "Harmonic Minor", "intervals": [0,2,3,5,7,8,11], "origin": "Western"},
  {"name": "Melodic Minor", "intervals": [0,2,3,5,7,9,11], "origin": "Western"},
  {"name": "Whole Tone", "intervals": [0,2,4,6,8,10], "origin": "Western/Impressionist"},
  {"name": "Diminished (Half-Whole)", "intervals": [0,1,3,4,6,7,9,10], "origin": "Western/Jazz"},
  {"name": "Diminished (Whole-Half)", "intervals": [0,2,3,5,6,8,9,11], "origin": "Western/Jazz"},
  {"name": "Augmented", "intervals": [0,3,4,7,8,11], "origin": "Western/Impressionist"},
  {"name": "Chromatic", "intervals": [0,1,2,3,4,5,6,7,8,9,10,11], "origin": "Western"},
  {"name": "Blues Hexatonic", "intervals": [0,3,5,6,7,10], "origin": "African-American"},
  {"name": "Minor Pentatonic", "intervals": [0,3,5,7,10], "origin": "Global"},
  {"name": "Major Pentatonic", "intervals": [0,2,4,7,9], "origin": "Global"},
  {"name": "Bebop Dominant", "intervals": [0,2,4,5,7,9,10,11], "origin": "American Jazz"},
  {"name": "Bebop Dorian", "intervals": [0,2,3,4,5,7,9,10], "origin": "American Jazz"},
  {"name": "Altered Dominant", "intervals": [0,1,3,4,6,8,10], "origin": "American Jazz"},
  {"name": "Maqam Hijaz", "intervals": [0,1,4,5,7,8,11], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Bayati", "intervals": [0,2,3,5,7,8,10], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Saba", "intervals": [0,2,3,5,6,8,10], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Nahawand", "intervals": [0,2,3,5,7,8,11], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Kurd", "intervals": [0,1,3,5,7,8,10], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Rast", "intervals": [0,2,4,5,7,9,10], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Sikah", "intervals": [0,1,4,5,7,8,10], "origin": "Middle Eastern/Arabic"},
  {"name": "Maqam Ajam", "intervals": [0,2,4,5,7,9,11], "origin": "Middle Eastern/Arabic"},
  {"name": "Hicaz", "intervals": [0,1,4,5,7,9,10], "origin": "Turkish"},
  {"name": "Ussak", "intervals": [0,2,3,5,7,8,10], "origin": "Turkish"},
  {"name": "Nihavend", "intervals": [0,2,3,5,7,8,11], "origin": "Turkish"},
  {"name": "Huseyni", "intervals": [0,2,3,5,7,9,10], "origin": "Turkish"},
  {"name": "Raga Bhairav", "intervals": [0,1,4,5,7,8,11], "origin": "Indian/Hindustani"},
  {"name": "Raga Todi", "intervals": [0,1,3,6,7,8,11], "origin": "Indian/Hindustani"},
  {"name": "Raga Marwa", "intervals": [0,1,4,6,7,9,11], "origin": "Indian/Hindustani"},
  {"name": "Raga Purvi", "intervals": [0,1,4,6,7,8,11], "origin": "Indian/Hindustani"},
  {"name": "Raga Kafi", "intervals": [0,2,3,5,7,9,10], "origin": "Indian/Hindustani"},
  {"name": "Raga Bhairavi", "intervals": [0,1,3,5,7,8,10], "origin": "Indian/Hindustani"},
  {"name": "Raga Yaman", "intervals": [0,2,4,6,7,9,11], "origin": "Indian/Hindustani"},
  {"name": "Raga Malkauns", "intervals": [0,3,5,8,10], "origin": "Indian/Hindustani"},
  {"name": "Hirajoshi", "intervals": [0,4,6,7,11], "origin": "Japanese"},
  {"name": "Miyako-bushi", "intervals": [0,1,5,7,8], "origin": "Japanese"},
  {"name": "In", "intervals": [0,1,5,7,8], "origin": "Japanese"},
  {"name": "Yo", "intervals": [0,2,5,7,9], "origin": "Japanese"},
  {"name": "Iwato", "intervals": [0,1,5,6,10], "origin": "Japanese"},
  {"name": "Kumoi", "intervals": [0,2,3,7,9], "origin": "Japanese"},
  {"name": "Pelog", "intervals": [0,1,3,7,8], "origin": "Indonesian/Javanese"},
  {"name": "Slendro", "intervals": [0,2,5,7,10], "origin": "Indonesian/Javanese"},
  {"name": "Chinese Gong", "intervals": [0,2,4,7,9], "origin": "Chinese"},
  {"name": "Chinese Shang", "intervals": [0,2,5,7,10], "origin": "Chinese"},
  {"name": "Chinese Jue", "intervals": [0,3,5,8,10], "origin": "Chinese"},
  {"name": "Chinese Zhi", "intervals": [0,2,5,7,9], "origin": "Chinese"},
  {"name": "Chinese Yu", "intervals": [0,3,5,7,10], "origin": "Chinese"},
  {"name": "Ethiopic Tizita Minor", "intervals": [0,2,3,7,8], "origin": "Ethiopian"},
  {"name": "Ethiopic Tizita Major", "intervals": [0,2,4,7,9], "origin": "Ethiopian"},
  {"name": "Ethiopic Ambassel", "intervals": [0,2,3,7,8], "origin": "Ethiopian"},
  {"name": "Ethiopic Anchihoye", "intervals": [0,3,5,7,10], "origin": "Ethiopian"},
  {"name": "Hungarian Minor", "intervals": [0,2,3,6,7,8,11], "origin": "Eastern European"},
  {"name": "Hungarian Major", "intervals": [0,3,4,6,7,9,10], "origin": "Eastern European"},
  {"name": "Romanian Minor", "intervals": [0,2,3,6,7,9,10], "origin": "Eastern European"},
  {"name": "Ukrainian Dorian", "intervals": [0,2,3,6,7,9,10], "origin": "Eastern European"},
  {"name": "Byzantine", "intervals": [0,1,4,5,7,8,11], "origin": "Eastern European/Greek"},
  {"name": "Double Harmonic", "intervals": [0,1,4,5,7,8,11], "origin": "Eastern European"},
  {"name": "Neapolitan Major", "intervals": [0,1,3,5,7,9,11], "origin": "Italian"},
  {"name": "Neapolitan Minor", "intervals": [0,1,3,5,7,8,11], "origin": "Italian"},
  {"name": "Enigmatic", "intervals": [0,1,4,6,8,10,11], "origin": "Italian/Verdi"},
  {"name": "Prometheus", "intervals": [0,2,4,6,9,10], "origin": "Russian/Scriabin"},
  {"name": "Tritone", "intervals": [0,1,4,6,7,10], "origin": "Synthetic"},
  {"name": "Messiaen Mode 2", "intervals": [0,1,3,4,6,7,9,10], "origin": "French/Messiaen"},
  {"name": "Messiaen Mode 3", "intervals": [0,2,3,4,6,7,8,10,11], "origin": "French/Messiaen"},
  {"name": "Messiaen Mode 4", "intervals": [0,1,2,5,6,7,8,11], "origin": "French/Messiaen"},
  {"name": "Messiaen Mode 5", "intervals": [0,1,5,6,7,11], "origin": "French/Messiaen"},
  {"name": "Messiaen Mode 6", "intervals": [0,2,4,5,6,8,10,11], "origin": "French/Messiaen"},
  {"name": "Mystic Chord", "intervals": [0,2,4,6,9,10], "origin": "Russian/Scriabin"},
  {"name": "Phrygian Dominant", "intervals": [0,1,4,5,7,8,10], "origin": "Flamenco/Spanish"},
  {"name": "Persian", "intervals": [0,1,4,5,6,8,11], "origin": "Persian"},
  {"name": "Arabian", "intervals": [0,2,4,5,6,8,10], "origin": "Arabian"},
  {"name": "Balinese", "intervals": [0,1,3,7,8], "origin": "Indonesian/Balinese"},
  {"name": "Algerian", "intervals": [0,2,3,6,7,8,11], "origin": "North African"}
]
```

That's 78 scales. Include all of them.

**Step 2: Commit**

```bash
git add midi-bot/scales.json
git commit -m "feat(midi-bot): add 78 world scales database"
```

---

## Task 3: Instruments Database

**Files:**
- Create: `midi-bot/instruments.json`

**Step 1: Create `instruments.json`**

Group General MIDI instruments into melody and chord categories. The LLM picks from these.

```json
{
  "melody": [
    {"program": 0, "name": "Acoustic Grand Piano"},
    {"program": 4, "name": "Electric Piano"},
    {"program": 6, "name": "Harpsichord"},
    {"program": 11, "name": "Vibraphone"},
    {"program": 13, "name": "Xylophone"},
    {"program": 22, "name": "Harmonica"},
    {"program": 24, "name": "Acoustic Guitar (nylon)"},
    {"program": 25, "name": "Acoustic Guitar (steel)"},
    {"program": 26, "name": "Jazz Guitar"},
    {"program": 40, "name": "Violin"},
    {"program": 41, "name": "Viola"},
    {"program": 42, "name": "Cello"},
    {"program": 46, "name": "Orchestral Harp"},
    {"program": 56, "name": "Trumpet"},
    {"program": 57, "name": "Trombone"},
    {"program": 60, "name": "French Horn"},
    {"program": 64, "name": "Soprano Sax"},
    {"program": 65, "name": "Alto Sax"},
    {"program": 66, "name": "Tenor Sax"},
    {"program": 68, "name": "Oboe"},
    {"program": 69, "name": "English Horn"},
    {"program": 71, "name": "Clarinet"},
    {"program": 72, "name": "Piccolo"},
    {"program": 73, "name": "Flute"},
    {"program": 74, "name": "Recorder"},
    {"program": 75, "name": "Pan Flute"},
    {"program": 79, "name": "Ocarina"},
    {"program": 80, "name": "Lead (Square)"},
    {"program": 81, "name": "Lead (Sawtooth)"},
    {"program": 104, "name": "Sitar"},
    {"program": 105, "name": "Banjo"},
    {"program": 107, "name": "Koto"},
    {"program": 108, "name": "Kalimba"},
    {"program": 109, "name": "Bagpipe"},
    {"program": 110, "name": "Fiddle"},
    {"program": 111, "name": "Shanai"}
  ],
  "chords": [
    {"program": 0, "name": "Acoustic Grand Piano"},
    {"program": 4, "name": "Electric Piano"},
    {"program": 5, "name": "Electric Piano 2"},
    {"program": 6, "name": "Harpsichord"},
    {"program": 7, "name": "Clavinet"},
    {"program": 16, "name": "Drawbar Organ"},
    {"program": 17, "name": "Percussive Organ"},
    {"program": 18, "name": "Rock Organ"},
    {"program": 19, "name": "Church Organ"},
    {"program": 24, "name": "Acoustic Guitar (nylon)"},
    {"program": 25, "name": "Acoustic Guitar (steel)"},
    {"program": 26, "name": "Jazz Guitar"},
    {"program": 27, "name": "Clean Electric Guitar"},
    {"program": 46, "name": "Orchestral Harp"},
    {"program": 48, "name": "String Ensemble 1"},
    {"program": 49, "name": "String Ensemble 2"},
    {"program": 52, "name": "Choir Aahs"},
    {"program": 88, "name": "Pad (New Age)"},
    {"program": 89, "name": "Pad (Warm)"},
    {"program": 90, "name": "Pad (Polysynth)"},
    {"program": 92, "name": "Pad (Metallic)"},
    {"program": 94, "name": "Pad (Halo)"}
  ],
  "bass": [
    {"program": 32, "name": "Acoustic Bass"},
    {"program": 33, "name": "Electric Bass (finger)"},
    {"program": 34, "name": "Electric Bass (pick)"},
    {"program": 35, "name": "Fretless Bass"},
    {"program": 36, "name": "Slap Bass 1"},
    {"program": 37, "name": "Slap Bass 2"},
    {"program": 38, "name": "Synth Bass 1"},
    {"program": 39, "name": "Synth Bass 2"},
    {"program": 43, "name": "Contrabass"},
    {"program": 87, "name": "Lead (Bass + Lead)"}
  ]
}
```

**Step 2: Commit**

```bash
git add midi-bot/instruments.json
git commit -m "feat(midi-bot): add General MIDI instruments database"
```

---

## Task 4: Musical Inspirations + Prompt Template

**Files:**
- Create: `midi-bot/inspirations.txt`
- Create: `midi-bot/prompt_template.txt`

**Step 1: Create `inspirations.txt`**

Musical vibes and scenarios (30+ entries):

```
lo-fi jazz elevator music
industrial machinery rhythm
music box in a thunderstorm
gamelan orchestra on a space station
baroque harpsichord played underwater
free jazz in a hospital waiting room
church organ at a demolition derby
steel drums on a frozen lake
honky-tonk piano in an empty cathedral
ambient drone from a broken refrigerator
spaghetti western soundtrack played backwards
medieval lute at a rave
wind chimes in a wind tunnel
mariachi band on the moon
ragtime piano during an earthquake
synthesizer solo in a cave
calliope music at midnight
gospel choir in a submarine
didgeridoo in a parking garage
theremin at a funeral
toy piano concerto for anxious adults
pipe organ vs drum machine
harp played with oven mitts
accordion music for the apocalypse
jazz flute in a tornado
music box lullaby for insomniacs
banjo bluegrass from another dimension
orchestral swell in a bathroom
zither solo at rush hour
handpan meditation gone wrong
```

**Step 2: Create `prompt_template.txt`**

The template includes the full scale list and instrument list as context for the LLM. These are injected at runtime from `scales.json` and `instruments.json`.

```
You are a surrealist composer with severe internet brain rot. You select unusual musical parameters inspired by news headlines.

Given the headlines and inspirations below, output a JSON object with these exact keys:
- "scale": one scale name from the SCALES list below (prefer unusual, non-Western scales — DO NOT keep picking the same ones)
- "root": a root note (e.g. "C", "F#", "Bb") — vary this, don't always pick C or A
- "chords": an array of exactly 4 chord symbols that work with the chosen scale (e.g. ["Am", "Dm7", "G7", "Cmaj7"])
- "tempo": a number between 40 and 200
- "temperature": a number between 0.5 and 1.5 (how wild the AI-generated melody and drums should be)
- "melody_instrument": a MIDI program number from the MELODY INSTRUMENTS list below
- "chord_instrument": a MIDI program number from the CHORD INSTRUMENTS list below
- "description": a single surreal sentence inspired by the headlines (with 1-3 emojis, Slack formatting allowed)

Output ONLY the JSON. No explanation. No markdown code fence. Just the raw JSON object.

SCALES:
{scales}

MELODY INSTRUMENTS:
{melody_instruments}

CHORD INSTRUMENTS:
{chord_instruments}

---

Today's news headlines:
{headlines}

Musical inspiration for today:
{inspirations}
```

**Step 3: Commit**

```bash
git add midi-bot/inspirations.txt midi-bot/prompt_template.txt
git commit -m "feat(midi-bot): add musical inspirations and LLM prompt template"
```

---

## Task 5: Python Config Module

**Files:**
- Create: `midi-bot/src/config.py`
- Create: `midi-bot/tests/__init__.py`
- Create: `midi-bot/tests/test_config.py`

**Step 1: Write the failing test**

```python
# midi-bot/tests/test_config.py
import pytest
from pathlib import Path
from unittest.mock import patch
from src.config import load_config, merge_cli_args


def test_load_config_defaults(tmp_path):
    """Config loads with defaults when no YAML file exists."""
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config["slack"]["channel"] == "#midieval"
    assert config["prompt"]["model"] == "meta-llama/Llama-3.3-70B-Instruct"
    assert config["prompt"]["temperature"] == 1.0
    assert config["prompt"]["max_headlines"] == 10


def test_load_config_from_yaml(tmp_path):
    """Config loads values from YAML file."""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text('slack:\n  channel: "#test"\nprompt:\n  temperature: 0.5\n')
    config = load_config(yaml_file)
    assert config["slack"]["channel"] == "#test"
    assert config["prompt"]["temperature"] == 0.5
    # Defaults still present for unset keys
    assert config["prompt"]["model"] == "meta-llama/Llama-3.3-70B-Instruct"


def test_merge_cli_args():
    """CLI args override config values."""
    config = {"slack": {"channel": "#midieval"}, "prompt": {"temperature": 1.0},
              "inspirations": {"pick_count": 2}, "sources": ["reuters"]}

    class Args:
        channel = "#override"
        temperature = 0.8
        sources = None
        no_inspirations = False

    result = merge_cli_args(config, Args())
    assert result["slack"]["channel"] == "#override"
    assert result["prompt"]["temperature"] == 0.8
```

**Step 2: Run test to verify it fails**

```bash
cd midi-bot && python -m pytest tests/test_config.py -v
```

Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# midi-bot/src/config.py
"""Configuration loader with YAML support and CLI overrides."""
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = {
    "slack": {
        "channel": "#midieval",
    },
    "prompt": {
        "temperature": 1.0,
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "max_headlines": 10,
    },
    "inspirations": {
        "file": "inspirations.txt",
        "pick_count": 2,
    },
    "sources": [
        "reuters", "foxnews", "cnn", "bbc",
        "ft", "npr", "guardian", "breitbart"
    ],
}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load config from YAML file, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)
    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_cli_args(config: dict[str, Any], args) -> dict[str, Any]:
    """Merge CLI arguments into config, overriding where specified."""
    if hasattr(args, 'channel') and args.channel:
        config["slack"]["channel"] = args.channel
    if hasattr(args, 'temperature') and args.temperature is not None:
        config["prompt"]["temperature"] = args.temperature
    if hasattr(args, 'sources') and args.sources:
        config["sources"] = args.sources.split(",")
    if hasattr(args, 'no_inspirations') and args.no_inspirations:
        config["inspirations"]["pick_count"] = 0
    return config
```

**Step 4: Run test to verify it passes**

```bash
cd midi-bot && python -m pytest tests/test_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add midi-bot/src/config.py midi-bot/tests/__init__.py midi-bot/tests/test_config.py
git commit -m "feat(midi-bot): add config module with tests"
```

---

## Task 6: Python Generator Module (LLM → Structured JSON)

**Files:**
- Create: `midi-bot/src/generator.py`
- Create: `midi-bot/tests/test_generator.py`

This module calls Llama 3.3 70B via HuggingFace, injecting the scales and instruments into the prompt template, and parses the structured JSON response.

**Step 1: Write the failing test**

```python
# midi-bot/tests/test_generator.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.generator import (
    load_template, build_llm_prompt, parse_llm_response,
    validate_params, generate_music_params
)


SAMPLE_SCALES = [
    {"name": "Hirajoshi", "intervals": [0,4,6,7,11], "origin": "Japanese"},
    {"name": "Blues Hexatonic", "intervals": [0,3,5,6,7,10], "origin": "African-American"},
]

SAMPLE_INSTRUMENTS = {
    "melody": [{"program": 73, "name": "Flute"}],
    "chords": [{"program": 0, "name": "Acoustic Grand Piano"}],
    "bass": [{"program": 32, "name": "Acoustic Bass"}],
}


def test_load_template(tmp_path):
    """Template splits on --- into system and user parts."""
    template_file = tmp_path / "template.txt"
    template_file.write_text("System prompt here\n---\nUser prompt {headlines}")
    system, user = load_template(template_file)
    assert "System prompt" in system
    assert "{headlines}" in user


def test_build_llm_prompt():
    """Prompt injects headlines, inspirations, scales, and instruments."""
    template = "Headlines:\n{headlines}\nInspirations:\n{inspirations}\nScales:\n{scales}\nMelody:\n{melody_instruments}\nChords:\n{chord_instruments}"
    prompt = build_llm_prompt(
        template,
        headlines=["Test headline"],
        inspirations=["lo-fi jazz"],
        scales=SAMPLE_SCALES,
        instruments=SAMPLE_INSTRUMENTS,
    )
    assert "Test headline" in prompt
    assert "lo-fi jazz" in prompt
    assert "Hirajoshi" in prompt
    assert "Flute" in prompt


def test_parse_llm_response_valid():
    """Valid JSON response parses correctly."""
    response = json.dumps({
        "scale": "Hirajoshi", "root": "D",
        "chords": ["Dm", "Am", "Em", "Dm"],
        "tempo": 95, "temperature": 1.2,
        "melody_instrument": 73, "chord_instrument": 0,
        "description": "A test description"
    })
    result = parse_llm_response(response)
    assert result["scale"] == "Hirajoshi"
    assert result["tempo"] == 95


def test_parse_llm_response_with_code_fence():
    """JSON wrapped in markdown code fence still parses."""
    response = '```json\n{"scale": "Hirajoshi", "root": "C", "chords": ["Cm"], "tempo": 120, "temperature": 1.0, "melody_instrument": 0, "chord_instrument": 0, "description": "test"}\n```'
    result = parse_llm_response(response)
    assert result["scale"] == "Hirajoshi"


def test_parse_llm_response_invalid():
    """Invalid JSON raises ValueError."""
    with pytest.raises(ValueError):
        parse_llm_response("not json at all")


def test_validate_params_valid():
    """Valid params pass validation."""
    params = {
        "scale": "Hirajoshi", "root": "D",
        "chords": ["Dm", "Am", "Em", "Dm"],
        "tempo": 95, "temperature": 1.2,
        "melody_instrument": 73, "chord_instrument": 0,
        "description": "A test"
    }
    # Should not raise
    validate_params(params, SAMPLE_SCALES, SAMPLE_INSTRUMENTS)


def test_validate_params_bad_scale():
    """Unknown scale raises ValueError."""
    params = {
        "scale": "Nonexistent Scale", "root": "C",
        "chords": ["Cm"], "tempo": 120, "temperature": 1.0,
        "melody_instrument": 73, "chord_instrument": 0,
        "description": "test"
    }
    with pytest.raises(ValueError, match="scale"):
        validate_params(params, SAMPLE_SCALES, SAMPLE_INSTRUMENTS)


def test_validate_params_bad_tempo():
    """Tempo out of range raises ValueError."""
    params = {
        "scale": "Hirajoshi", "root": "C",
        "chords": ["Cm"], "tempo": 300, "temperature": 1.0,
        "melody_instrument": 73, "chord_instrument": 0,
        "description": "test"
    }
    with pytest.raises(ValueError, match="tempo"):
        validate_params(params, SAMPLE_SCALES, SAMPLE_INSTRUMENTS)
```

**Step 2: Run test to verify it fails**

```bash
cd midi-bot && python -m pytest tests/test_generator.py -v
```

Expected: FAIL with ModuleNotFoundError

**Step 3: Write implementation**

```python
# midi-bot/src/generator.py
"""Music parameter generator using Hugging Face Inference API."""
import json
import logging
import re
from pathlib import Path
from typing import Any

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


def load_scales(scales_path: Path) -> list[dict]:
    """Load scales database from JSON file."""
    return json.loads(scales_path.read_text())


def load_instruments(instruments_path: Path) -> dict[str, list[dict]]:
    """Load instruments database from JSON file."""
    return json.loads(instruments_path.read_text())


def load_template(template_path: Path) -> tuple[str, str]:
    """Load prompt template. Returns (system_prompt, user_template)."""
    content = template_path.read_text()
    parts = content.split("---", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", content.strip()


def build_llm_prompt(
    template: str,
    headlines: list[str],
    inspirations: list[str],
    scales: list[dict],
    instruments: dict[str, list[dict]],
) -> str:
    """Build the prompt with all context injected."""
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    inspirations_text = "\n".join(f"- {i}" for i in inspirations) if inspirations else "(none)"
    scales_text = "\n".join(f"- {s['name']} ({s['origin']})" for s in scales)
    melody_text = "\n".join(f"- {i['program']}: {i['name']}" for i in instruments["melody"])
    chords_text = "\n".join(f"- {i['program']}: {i['name']}" for i in instruments["chords"])

    return template.format(
        headlines=headlines_text,
        inspirations=inspirations_text,
        scales=scales_text,
        melody_instruments=melody_text,
        chord_instruments=chords_text,
    )


def parse_llm_response(response: str) -> dict[str, Any]:
    """Parse the LLM's JSON response, handling code fences and think tags."""
    # Strip think tags
    cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL).strip()
    # Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response[:200]}")


def validate_params(
    params: dict[str, Any],
    scales: list[dict],
    instruments: dict[str, list[dict]],
) -> None:
    """Validate LLM-generated params. Raises ValueError on invalid params."""
    scale_names = {s["name"] for s in scales}
    if params.get("scale") not in scale_names:
        raise ValueError(f"Unknown scale: {params.get('scale')}")

    tempo = params.get("tempo", 0)
    if not (40 <= tempo <= 200):
        raise ValueError(f"Invalid tempo: {tempo} (must be 40-200)")

    temp = params.get("temperature", 0)
    if not (0.5 <= temp <= 1.5):
        raise ValueError(f"Invalid temperature: {temp} (must be 0.5-1.5)")

    valid_melody = {i["program"] for i in instruments["melody"]}
    if params.get("melody_instrument") not in valid_melody:
        raise ValueError(f"Invalid melody_instrument: {params.get('melody_instrument')}")

    valid_chords = {i["program"] for i in instruments["chords"]}
    if params.get("chord_instrument") not in valid_chords:
        raise ValueError(f"Invalid chord_instrument: {params.get('chord_instrument')}")

    if not isinstance(params.get("chords"), list) or len(params["chords"]) != 4:
        raise ValueError(f"chords must be an array of exactly 4 chord symbols")


def generate_music_params(
    headlines: list[str],
    inspirations: list[str],
    scales: list[dict],
    instruments: dict[str, list[dict]],
    model: str,
    temperature: float,
    api_key: str,
    template_path: Path = None,
) -> dict[str, Any]:
    """Generate structured music parameters via LLM."""
    client = InferenceClient(token=api_key)

    if template_path is None:
        template_path = Path(__file__).parent.parent / "prompt_template.txt"

    system_prompt, user_template = load_template(template_path)
    user_prompt = build_llm_prompt(user_template, headlines, inspirations, scales, instruments)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    response = client.chat_completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=1000,
    )

    result_text = response.choices[0].message.content.strip()
    logger.info(f"LLM response: {result_text[:200]}")

    params = parse_llm_response(result_text)
    validate_params(params, scales, instruments)

    return params
```

**Step 4: Run test to verify it passes**

```bash
cd midi-bot && python -m pytest tests/test_generator.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add midi-bot/src/generator.py midi-bot/tests/test_generator.py
git commit -m "feat(midi-bot): add LLM music parameter generator with tests"
```

---

## Task 7: Python Slack Poster Module (File Upload)

**Files:**
- Create: `midi-bot/src/slack_poster.py`
- Create: `midi-bot/tests/test_slack_poster.py`

**Step 1: Write the failing test**

```python
# midi-bot/tests/test_slack_poster.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from src.slack_poster import format_message, post_midi_to_slack


def test_format_message():
    """Message includes all metadata."""
    params = {
        "scale": "Hirajoshi", "root": "D", "tempo": 95,
        "temperature": 1.2, "melody_instrument": 73,
        "chord_instrument": 0, "chords": ["Dm", "Am", "Em", "Dm"],
        "description": "A test description"
    }
    instruments = {
        "melody": [{"program": 73, "name": "Flute"}],
        "chords": [{"program": 0, "name": "Acoustic Grand Piano"}],
        "bass": [{"program": 32, "name": "Acoustic Bass"}],
    }
    msg = format_message(params, instruments)
    assert "Hirajoshi" in msg
    assert "D" in msg
    assert "95 BPM" in msg
    assert "Flute" in msg
    assert "Dm" in msg
    assert "A test description" in msg


@patch("src.slack_poster.WebClient")
def test_post_midi_to_slack(mock_client_cls, tmp_path):
    """Posts main message then 4 threaded file uploads."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat_postMessage.return_value = {"ts": "123.456"}

    # Create fake MIDI files
    midi_dir = tmp_path
    for name in ["melody.mid", "drums.mid", "bass.mid", "chords.mid"]:
        (midi_dir / name).write_bytes(b"fake midi")

    params = {
        "scale": "Hirajoshi", "root": "D", "tempo": 95,
        "temperature": 1.2, "melody_instrument": 73,
        "chord_instrument": 0, "chords": ["Dm", "Am", "Em", "Dm"],
        "description": "test"
    }
    instruments = {
        "melody": [{"program": 73, "name": "Flute"}],
        "chords": [{"program": 0, "name": "Acoustic Grand Piano"}],
        "bass": [{"program": 32, "name": "Acoustic Bass"}],
    }

    result = post_midi_to_slack(
        params=params,
        instruments=instruments,
        midi_dir=midi_dir,
        channel="#test",
        token="xoxb-fake",
    )
    assert result is True
    # 1 main message + 4 file uploads
    mock_client.chat_postMessage.assert_called_once()
    assert mock_client.files_upload_v2.call_count == 4
```

**Step 2: Run test to verify it fails**

```bash
cd midi-bot && python -m pytest tests/test_slack_poster.py -v
```

Expected: FAIL

**Step 3: Write implementation**

```python
# midi-bot/src/slack_poster.py
"""Slack poster with MIDI file upload support."""
import logging
from pathlib import Path

from slack_sdk import WebClient

logger = logging.getLogger(__name__)

TRACK_LABELS = {
    "melody": ":musical_keyboard: Melody",
    "drums": ":drum_with_drumsticks: Drums",
    "bass": ":guitar: Bass",
    "chords": ":musical_score: Chords",
}


def _find_instrument_name(program: int, instrument_list: list[dict]) -> str:
    """Look up instrument name by MIDI program number."""
    for inst in instrument_list:
        if inst["program"] == program:
            return inst["name"]
    return f"MIDI {program}"


def format_message(params: dict, instruments: dict) -> str:
    """Format the main Slack message with all metadata."""
    melody_name = _find_instrument_name(params["melody_instrument"], instruments["melody"])
    chord_name = _find_instrument_name(params["chord_instrument"], instruments["chords"])
    chords_str = "  ".join(params["chords"])

    lines = [
        f":musical_note: *Daily MIDI* — {params['scale']} in {params['root']} ({params['tempo']} BPM)",
        f"_{params['description']}_",
        "",
        f":musical_keyboard: Melody — ImprovRNN, {melody_name} (MIDI {params['melody_instrument']}), temperature {params['temperature']}",
        f":drum_with_drumsticks: Drums — DrumsRNN, temperature {params['temperature']}",
        f":guitar: Bass — Programmatic from chord roots",
        f":musical_score: Chords — {chords_str}",
    ]
    return "\n".join(lines)


def post_midi_to_slack(
    params: dict,
    instruments: dict,
    midi_dir: Path,
    channel: str,
    token: str,
) -> bool:
    """Post main message + 4 MIDI files as threaded replies."""
    try:
        client = WebClient(token=token)

        # Post main message
        message = format_message(params, instruments)
        resp = client.chat_postMessage(channel=channel, text=message)
        thread_ts = resp["ts"]
        logger.info(f"Posted main message to {channel}")

        # Upload each MIDI file as a threaded reply
        for track in ["melody", "drums", "bass", "chords"]:
            filepath = midi_dir / f"{track}.mid"
            if not filepath.exists():
                logger.error(f"Missing MIDI file: {filepath}")
                return False

            client.files_upload_v2(
                channel=channel,
                file=str(filepath),
                filename=f"{track}.mid",
                initial_comment=TRACK_LABELS[track],
                thread_ts=thread_ts,
            )
            logger.info(f"Uploaded {track}.mid")

        return True
    except Exception as e:
        logger.error(f"Failed to post to Slack: {e}")
        return False
```

**Step 4: Run test to verify it passes**

```bash
cd midi-bot && python -m pytest tests/test_slack_poster.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add midi-bot/src/slack_poster.py midi-bot/tests/test_slack_poster.py
git commit -m "feat(midi-bot): add Slack file upload poster with tests"
```

---

## Task 8: Node.js MIDI Generator

**Files:**
- Create: `midi-bot/generate_midi.js`

This is the core MIDI generation script. It reads JSON params from stdin, generates 4 MIDI files, and writes them to a specified output directory.

**Step 1: Install Node.js dependencies**

```bash
cd midi-bot && npm install
```

Note: `@tensorflow/tfjs-node` may fail to build on some systems. If it does, the script still works with the pure JS TensorFlow backend (just slower). If the build fails, remove it from package.json and it will fall back automatically.

**Step 2: Create `generate_midi.js`**

```javascript
#!/usr/bin/env node
/**
 * MIDI generator using Magenta.js (ImprovRNN, DrumsRNN) + programmatic bass/chords.
 *
 * Reads JSON params from stdin, writes 4 MIDI files to the output directory.
 *
 * Usage: echo '{"scale":"Hirajoshi",...}' | node generate_midi.js /tmp/midi-output
 */

const fs = require('fs');
const path = require('path');
const { Note, Chord } = require('tonal');

// Magenta.js imports (server-side Node.js paths)
const mm = require('@magenta/music/node/music_rnn');
const core = require('@magenta/music/node/core');

const IMPROV_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/chord_pitches_improv';
const DRUMS_CHECKPOINT = 'https://storage.googleapis.com/magentadata/js/checkpoints/music_rnn/drum_kit_rnn';

const STEPS_PER_QUARTER = 4;
const BARS = 4;
const BEATS_PER_BAR = 4;
const TOTAL_STEPS = BARS * BEATS_PER_BAR * STEPS_PER_QUARTER; // 64

// ── Scale quantization ──────────────────────────────────────────────────

function buildScalePitches(root, intervals, minPitch = 36, maxPitch = 96) {
  const rootMidi = Note.midi(root + '0');
  const pitches = new Set();
  for (let octave = 0; octave < 10; octave++) {
    for (const interval of intervals) {
      const pitch = rootMidi + (octave * 12) + interval;
      if (pitch >= minPitch && pitch <= maxPitch) {
        pitches.add(pitch);
      }
    }
  }
  return Array.from(pitches).sort((a, b) => a - b);
}

function quantizeToScale(pitch, scalePitches) {
  let closest = scalePitches[0];
  let minDist = Math.abs(pitch - closest);
  for (const sp of scalePitches) {
    const dist = Math.abs(pitch - sp);
    if (dist < minDist) {
      minDist = dist;
      closest = sp;
    }
  }
  return closest;
}

// ── Melody generation (ImprovRNN) ───────────────────────────────────────

async function generateMelody(params, scalePitches) {
  const improvRnn = new mm.MusicRNN(IMPROV_CHECKPOINT);
  await improvRnn.initialize();

  // Minimal seed: one note in the scale
  const rootMidi = Note.midi(params.root + '4') || 60;
  const seedPitch = quantizeToScale(rootMidi, scalePitches);

  const seedSequence = {
    ticksPerQuarter: 220,
    totalTime: 0.5,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    notes: [{ pitch: seedPitch, startTime: 0.0, endTime: 0.5, velocity: 100 }],
  };

  const quantizedSeed = core.sequences.quantizeNoteSequence(seedSequence, STEPS_PER_QUARTER);

  const continuation = await improvRnn.continueSequence(
    quantizedSeed,
    TOTAL_STEPS,
    params.temperature,
    params.chords
  );

  // Post-process: quantize to scale + set instrument
  continuation.notes.forEach(n => {
    n.pitch = quantizeToScale(n.pitch, scalePitches);
    n.velocity = n.velocity || 100;
    n.program = params.melody_instrument;
    n.instrument = 0;
  });

  // Set tempo
  continuation.tempos = [{ time: 0, qpm: params.tempo }];

  improvRnn.dispose();
  return continuation;
}

// ── Drums generation (DrumsRNN) ─────────────────────────────────────────

async function generateDrums(params) {
  const drumsRnn = new mm.MusicRNN(DRUMS_CHECKPOINT);
  await drumsRnn.initialize();

  // Minimal seed: kick on beat 1
  const seedSequence = {
    ticksPerQuarter: 220,
    totalTime: 0.5,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    notes: [
      { pitch: 36, startTime: 0.0, endTime: 0.5, isDrum: true, velocity: 100 },
      { pitch: 42, startTime: 0.0, endTime: 0.5, isDrum: true, velocity: 80 },
    ],
  };

  const quantizedSeed = core.sequences.quantizeNoteSequence(seedSequence, STEPS_PER_QUARTER);

  const continuation = await drumsRnn.continueSequence(
    quantizedSeed,
    TOTAL_STEPS,
    params.temperature
  );

  continuation.notes.forEach(n => {
    n.velocity = n.velocity || 100;
    n.isDrum = true;
  });

  continuation.tempos = [{ time: 0, qpm: params.tempo }];

  drumsRnn.dispose();
  return continuation;
}

// ── Bass generation (programmatic) ──────────────────────────────────────

function generateBass(params, scalePitches) {
  const bassPitches = scalePitches.filter(p => p >= 36 && p <= 60);
  const secondsPerBeat = 60.0 / params.tempo;
  const totalBeats = BARS * BEATS_PER_BAR;
  const beatsPerChord = totalBeats / params.chords.length;

  const notes = [];
  const patterns = ['root-fifth', 'walking', 'syncopated'];
  const pattern = patterns[Math.floor(Math.random() * patterns.length)];

  for (let ci = 0; ci < params.chords.length; ci++) {
    const chordInfo = Chord.get(params.chords[ci]);
    const rootNote = chordInfo.tonic || params.root;
    const rootMidi = Note.midi(rootNote + '2') || 48;
    const root = quantizeToScale(rootMidi, bassPitches.length ? bassPitches : scalePitches);
    const fifth = quantizeToScale(rootMidi + 7, bassPitches.length ? bassPitches : scalePitches);

    const chordStartBeat = ci * beatsPerChord;

    if (pattern === 'root-fifth') {
      for (let beat = 0; beat < beatsPerChord; beat++) {
        const pitch = beat % 2 === 0 ? root : fifth;
        const startTime = (chordStartBeat + beat) * secondsPerBeat;
        notes.push({
          pitch, startTime, endTime: startTime + secondsPerBeat * 0.9,
          velocity: 100, program: 32, instrument: 0, isDrum: false,
        });
      }
    } else if (pattern === 'walking') {
      const walkNotes = [root, root + 2, fifth, fifth - 2].map(
        p => quantizeToScale(p, bassPitches.length ? bassPitches : scalePitches)
      );
      for (let beat = 0; beat < beatsPerChord; beat++) {
        const pitch = walkNotes[beat % walkNotes.length];
        const startTime = (chordStartBeat + beat) * secondsPerBeat;
        notes.push({
          pitch, startTime, endTime: startTime + secondsPerBeat * 0.9,
          velocity: 100, program: 32, instrument: 0, isDrum: false,
        });
      }
    } else {
      // syncopated: root on beat, rest, root on and-of-2, rest
      const startBeat1 = chordStartBeat;
      notes.push({
        pitch: root, startTime: startBeat1 * secondsPerBeat,
        endTime: (startBeat1 + 1.5) * secondsPerBeat,
        velocity: 100, program: 32, instrument: 0, isDrum: false,
      });
      if (beatsPerChord >= 3) {
        const startBeat2 = chordStartBeat + 2.5;
        notes.push({
          pitch: fifth, startTime: startBeat2 * secondsPerBeat,
          endTime: (startBeat2 + 1) * secondsPerBeat,
          velocity: 90, program: 32, instrument: 0, isDrum: false,
        });
      }
    }
  }

  return {
    ticksPerQuarter: 220,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    totalTime: totalBeats * secondsPerBeat,
    notes,
  };
}

// ── Chords generation (programmatic) ────────────────────────────────────

function generateChords(params, scalePitches) {
  const secondsPerBeat = 60.0 / params.tempo;
  const totalBeats = BARS * BEATS_PER_BAR;
  const beatsPerChord = totalBeats / params.chords.length;

  const notes = [];
  const rhythms = ['whole', 'half', 'comp'];
  const rhythm = rhythms[Math.floor(Math.random() * rhythms.length)];

  for (let ci = 0; ci < params.chords.length; ci++) {
    const chordInfo = Chord.get(params.chords[ci]);
    if (chordInfo.empty) continue;

    // Voice the chord at octave 4
    const chordNotes = chordInfo.notes.map(noteName => {
      const midi = Note.midi(noteName + '4');
      return midi ? quantizeToScale(midi, scalePitches) : null;
    }).filter(Boolean);

    const chordStartBeat = ci * beatsPerChord;

    if (rhythm === 'whole') {
      const startTime = chordStartBeat * secondsPerBeat;
      const endTime = (chordStartBeat + beatsPerChord) * secondsPerBeat;
      for (const pitch of chordNotes) {
        notes.push({
          pitch, startTime, endTime: endTime - 0.05,
          velocity: 80, program: params.chord_instrument, instrument: 0, isDrum: false,
        });
      }
    } else if (rhythm === 'half') {
      for (let h = 0; h < 2; h++) {
        const startTime = (chordStartBeat + h * (beatsPerChord / 2)) * secondsPerBeat;
        const endTime = (chordStartBeat + (h + 1) * (beatsPerChord / 2)) * secondsPerBeat;
        for (const pitch of chordNotes) {
          notes.push({
            pitch, startTime, endTime: endTime - 0.05,
            velocity: h === 0 ? 80 : 70, program: params.chord_instrument, instrument: 0, isDrum: false,
          });
        }
      }
    } else {
      // comp: hit on beat 1, rest, hit on and-of-2, hit on beat 4
      const hits = [0, 1.5, 3];
      const durations = [1.0, 1.0, 1.0];
      for (let h = 0; h < hits.length && hits[h] < beatsPerChord; h++) {
        const startTime = (chordStartBeat + hits[h]) * secondsPerBeat;
        const endTime = startTime + durations[h] * secondsPerBeat;
        for (const pitch of chordNotes) {
          notes.push({
            pitch, startTime, endTime: Math.min(endTime, (chordStartBeat + beatsPerChord) * secondsPerBeat) - 0.05,
            velocity: h === 0 ? 85 : 70, program: params.chord_instrument, instrument: 0, isDrum: false,
          });
        }
      }
    }
  }

  return {
    ticksPerQuarter: 220,
    tempos: [{ time: 0, qpm: params.tempo }],
    timeSignatures: [{ time: 0, numerator: 4, denominator: 4 }],
    totalTime: totalBeats * secondsPerBeat,
    notes,
  };
}

// ── Main ────────────────────────────────────────────────────────────────

async function main() {
  const outputDir = process.argv[2];
  if (!outputDir) {
    console.error('Usage: node generate_midi.js <output-dir>');
    process.exit(1);
  }

  // Read params from stdin
  const input = fs.readFileSync(0, 'utf-8');
  const params = JSON.parse(input);

  console.log(`Generating MIDI: ${params.scale} in ${params.root}, ${params.tempo} BPM`);

  // Load scale intervals from params (passed through from scales.json by Python)
  const scalePitches = buildScalePitches(params.root, params.scale_intervals);

  // Ensure output directory exists
  fs.mkdirSync(outputDir, { recursive: true });

  // Generate all 4 tracks
  console.log('Generating melody (ImprovRNN)...');
  const melody = await generateMelody(params, scalePitches);
  fs.writeFileSync(
    path.join(outputDir, 'melody.mid'),
    Buffer.from(core.sequenceProtoToMidi(melody))
  );

  console.log('Generating drums (DrumsRNN)...');
  const drums = await generateDrums(params);
  fs.writeFileSync(
    path.join(outputDir, 'drums.mid'),
    Buffer.from(core.sequenceProtoToMidi(drums))
  );

  console.log('Generating bass (programmatic)...');
  const bass = generateBass(params, scalePitches);
  fs.writeFileSync(
    path.join(outputDir, 'bass.mid'),
    Buffer.from(core.sequenceProtoToMidi(bass))
  );

  console.log('Generating chords (programmatic)...');
  const chords = generateChords(params, scalePitches);
  fs.writeFileSync(
    path.join(outputDir, 'chords.mid'),
    Buffer.from(core.sequenceProtoToMidi(chords))
  );

  console.log('Done! Generated 4 MIDI files.');
}

main().catch(err => {
  console.error('MIDI generation failed:', err);
  process.exit(1);
});
```

**Step 3: Test manually**

```bash
cd midi-bot && echo '{"scale":"Hirajoshi","root":"D","scale_intervals":[0,4,6,7,11],"chords":["Dm","Am","Em","Dm"],"tempo":95,"temperature":1.0,"melody_instrument":73,"chord_instrument":0,"description":"test"}' | node generate_midi.js /tmp/midi-test
```

Expected: 4 `.mid` files in `/tmp/midi-test/`. Verify they open in a DAW or MIDI player.

**Step 4: Commit**

```bash
git add midi-bot/generate_midi.js
git commit -m "feat(midi-bot): add Node.js MIDI generator with Magenta.js"
```

---

## Task 9: Python Main Orchestrator

**Files:**
- Create: `midi-bot/bot.py`

This ties everything together: config, scraping (from surreal-prompt-bot), LLM call, Node.js subprocess, Slack upload.

**Step 1: Create `bot.py`**

```python
#!/usr/bin/env python3
"""Daily MIDI Bot - Generates 4 MIDI files and posts to Slack."""

import argparse
import json
import logging
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

# Add surreal-prompt-bot to path for scraper/sampler reuse
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "surreal-prompt-bot"))

from src.config import load_config, merge_cli_args
from src.generator import (
    generate_music_params, load_scales, load_instruments
)
from src.slack_poster import post_midi_to_slack

# Import scraper/sampler from surreal-prompt-bot
from src.scraper import scrape_all_sources
from src.sampler import load_inspirations, sample_inspirations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_midi_generation(params: dict, output_dir: Path) -> bool:
    """Run the Node.js MIDI generator as a subprocess."""
    script_path = Path(__file__).parent / "generate_midi.js"

    # Add scale_intervals to params for the Node.js script
    scales = load_scales(Path(__file__).parent / "scales.json")
    scale_entry = next((s for s in scales if s["name"] == params["scale"]), None)
    if not scale_entry:
        logger.error(f"Scale not found: {params['scale']}")
        return False

    node_params = {**params, "scale_intervals": scale_entry["intervals"]}

    try:
        result = subprocess.run(
            ["node", str(script_path), str(output_dir)],
            input=json.dumps(node_params),
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent),
        )
        logger.info(f"Node.js stdout: {result.stdout}")
        if result.returncode != 0:
            logger.error(f"Node.js stderr: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("MIDI generation timed out (5 min)")
        return False
    except Exception as e:
        logger.error(f"Failed to run Node.js generator: {e}")
        return False


def run_bot(args) -> int:
    """Main bot logic. Returns exit code."""
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config
    config = load_config(config_path)
    config = merge_cli_args(config, args)

    # Get API keys
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        logger.error("HF_TOKEN environment variable not set")
        return 1

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token and not args.dry_run:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    # Scrape headlines (reusing surreal-prompt-bot scraper)
    logger.info(f"Scraping headlines from {len(config['sources'])} sources...")
    headlines = scrape_all_sources(config["sources"])
    if not headlines:
        logger.error("No headlines scraped from any source")
        return 1

    max_headlines = config["prompt"]["max_headlines"]
    if len(headlines) > max_headlines:
        headlines = random.sample(headlines, max_headlines)
    logger.info(f"Using {len(headlines)} headlines")

    # Sample musical inspirations
    inspirations = []
    if config["inspirations"]["pick_count"] > 0:
        insp_path = script_dir / config["inspirations"]["file"]
        all_inspirations = load_inspirations(insp_path)
        inspirations = sample_inspirations(
            all_inspirations, config["inspirations"]["pick_count"]
        )
        logger.info(f"Using inspirations: {inspirations}")

    # Load scales + instruments databases
    scales = load_scales(script_dir / "scales.json")
    instruments = load_instruments(script_dir / "instruments.json")

    # Generate music parameters via LLM
    logger.info("Generating music parameters via LLM...")
    params = generate_music_params(
        headlines=headlines,
        inspirations=inspirations,
        scales=scales,
        instruments=instruments,
        model=config["prompt"]["model"],
        temperature=config["prompt"]["temperature"],
        api_key=hf_token,
    )
    logger.info(f"Music params: {json.dumps(params, indent=2)}")

    # Generate MIDI files
    with tempfile.TemporaryDirectory() as midi_dir:
        midi_path = Path(midi_dir)
        logger.info("Generating MIDI files...")

        if not run_midi_generation(params, midi_path):
            logger.error("MIDI generation failed")
            return 1

        # Verify all 4 files exist
        for track in ["melody", "drums", "bass", "chords"]:
            if not (midi_path / f"{track}.mid").exists():
                logger.error(f"Missing generated file: {track}.mid")
                return 1

        logger.info("All 4 MIDI files generated successfully")

        if args.dry_run:
            logger.info("Dry run - not posting to Slack")
            # Copy files to a visible location for inspection
            import shutil
            dry_run_dir = script_dir / "dry-run-output"
            dry_run_dir.mkdir(exist_ok=True)
            for f in midi_path.glob("*.mid"):
                shutil.copy2(f, dry_run_dir / f.name)
            logger.info(f"MIDI files saved to {dry_run_dir}")
            return 0

        # Post to Slack
        channel = config["slack"]["channel"]
        logger.info(f"Posting to Slack channel {channel}...")
        if post_midi_to_slack(params, instruments, midi_path, channel, slack_token):
            logger.info("Successfully posted to Slack!")
            return 0
        else:
            logger.error("Failed to post to Slack")
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="Generate daily MIDI files and post to Slack"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate MIDI but don't post to Slack")
    parser.add_argument("--channel", help="Override Slack channel")
    parser.add_argument("--temperature", type=float, help="LLM temperature")
    parser.add_argument("--sources", help="Comma-separated news sources")
    parser.add_argument("--no-inspirations", action="store_true")
    parser.add_argument("--config", default="config.yaml")

    args = parser.parse_args()
    return run_bot(args)


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Test with dry run**

```bash
cd midi-bot && HF_TOKEN=your_token python bot.py --dry-run
```

Expected: LLM generates params, Node.js generates 4 MIDI files, saved to `dry-run-output/`.

**Step 3: Commit**

```bash
git add midi-bot/bot.py
git commit -m "feat(midi-bot): add main orchestrator"
```

---

## Task 10: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/daily-midi.yml`

**Step 1: Create workflow**

```yaml
name: Daily MIDI Bot

on:
  schedule:
    - cron: '0 16 * * *'  # 4pm UTC (8am PT)
  workflow_dispatch:  # Manual trigger

jobs:
  generate-midi:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: midi-bot/package-lock.json

      - name: Install Python dependencies
        run: pip install -r midi-bot/requirements.txt

      - name: Install Node.js dependencies
        run: cd midi-bot && npm ci

      - name: Generate and post MIDI
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        run: python midi-bot/bot.py
```

**Step 2: Commit**

```bash
git add .github/workflows/daily-midi.yml
git commit -m "feat(midi-bot): add GitHub Actions daily workflow"
```

---

## Task 11: Generate package-lock.json + End-to-End Dry Run

**Step 1: Generate lock file**

```bash
cd midi-bot && npm install
```

This creates `package-lock.json` (needed for `npm ci` in GitHub Actions).

**Step 2: Run full dry-run test**

```bash
cd midi-bot && HF_TOKEN=your_token python bot.py --dry-run
```

**Step 3: Verify output**

- Check `dry-run-output/` has 4 `.mid` files
- Open each in a MIDI player or DAW to verify they contain actual notes
- Check console output for the LLM-generated params (scale, chords, etc.)

**Step 4: Commit lock file**

```bash
git add midi-bot/package-lock.json
git commit -m "chore(midi-bot): add package-lock.json"
```

---

## Task 12: Add Slack `files:write` Scope

This is a manual step — cannot be automated.

**Step 1:** Go to https://api.slack.com/apps, select the existing bot app

**Step 2:** Navigate to OAuth & Permissions → Scopes → Bot Token Scopes

**Step 3:** Add `files:write` scope

**Step 4:** Reinstall the app to the workspace to apply the new scope

**Step 5:** Create the `#midieval` channel in Slack

**Step 6:** Invite the bot to `#midieval`

---

## Task 13: Live Test + Final Commit

**Step 1: Run with real Slack posting**

```bash
cd midi-bot && HF_TOKEN=your_token SLACK_BOT_TOKEN=your_slack_token python bot.py
```

**Step 2: Verify in Slack**

- Check `#midieval` for the main message with metadata
- Check thread for 4 MIDI file attachments
- Download and verify MIDI files play correctly

**Step 3: Trigger GitHub Actions workflow manually**

Go to Actions → Daily MIDI Bot → Run workflow. Verify it succeeds.

**Step 4: Final commit if any fixes were needed**

```bash
git add -A && git commit -m "fix(midi-bot): post-test fixes"
```

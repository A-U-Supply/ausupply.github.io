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

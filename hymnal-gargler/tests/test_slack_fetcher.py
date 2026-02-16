"""Tests for Slack fetcher."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from slack_fetcher import parse_midi_message


def test_parse_midi_message_valid():
    text = (
        ":musical_note: *Daily MIDI* — Hirajoshi in F# (145 BPM)\n"
        "_Bureaucrats dancing in the rain_\n\n"
        ":musical_keyboard: Melody — ImprovRNN, Koto (MIDI 107), temperature 1.2\n"
        ":drum_with_drumsticks: Drums — DrumsRNN, temperature 1.2\n"
        ":guitar: Bass — Programmatic\n"
        ":musical_score: Chords — F#m7 B7 E7 A7"
    )
    result = parse_midi_message(text)
    assert result is not None
    assert result["scale"] == "Hirajoshi"
    assert result["root"] == "F#"
    assert result["tempo"] == 145
    assert result["description"] == "Bureaucrats dancing in the rain"


def test_parse_midi_message_no_match():
    assert parse_midi_message("just a regular message") is None


def test_parse_midi_message_extracts_chords():
    text = "*Daily MIDI* — Blues in A (120 BPM)\n_test_\n:musical_score: Chords — Am Em G D"
    result = parse_midi_message(text)
    assert result["chords"] == ["Am", "Em", "G", "D"]

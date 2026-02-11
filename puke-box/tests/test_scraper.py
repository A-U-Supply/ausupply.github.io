import pytest
from scrape_midieval import parse_midi_message


def test_parse_midi_message():
    """Parse metadata from a Daily MIDI Slack message."""
    text = (
        ":musical_note: *Daily MIDI* — Maqam Nahawand in Bb (95 BPM)\n"
        "_A restless Tuesday in a bureaucracy that runs on reverb_\n"
        "\n"
        ":musical_keyboard: Melody — ImprovRNN, Flute (MIDI 73), temperature 1.2\n"
        ":drum_with_drumsticks: Drums — DrumsRNN, temperature 1.2\n"
        ":guitar: Bass — Programmatic from chord roots\n"
        ":musical_score: Chords — Bbm  Ebm7  Ab7  Dbmaj7"
    )
    result = parse_midi_message(text)
    assert result["scale"] == "Maqam Nahawand"
    assert result["root"] == "Bb"
    assert result["tempo"] == 95
    assert result["description"] == "A restless Tuesday in a bureaucracy that runs on reverb"
    assert result["chords"] == ["Bbm", "Ebm7", "Ab7", "Dbmaj7"]
    assert result["melody_instrument"] == 73
    assert result["temperature"] == 1.2


def test_parse_midi_message_returns_none_for_non_midi():
    """Non-Daily-MIDI messages return None."""
    assert parse_midi_message("just a random message") is None
    assert parse_midi_message(":wave: hello everyone") is None

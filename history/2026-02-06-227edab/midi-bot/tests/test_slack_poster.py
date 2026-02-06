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

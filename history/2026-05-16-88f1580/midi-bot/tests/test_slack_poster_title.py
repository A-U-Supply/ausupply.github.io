"""Tests for Slack poster song title formatting."""
from src.slack_poster import format_message


def test_with_song_title():
    params = {
        "scale": "Major", "root": "C", "tempo": 120,
        "description": "test", "melody_instrument": 0,
        "chord_instrument": 19, "temperature": 1.0,
        "chords": ["Cm", "Dm", "Em", "Fm"],
        "song_title": "Tip of the Fatberg",
    }
    instruments = {
        "melody": [{"program": 0, "name": "Piano"}],
        "chords": [{"program": 19, "name": "Church Organ"}],
    }
    msg = format_message(params, instruments)
    lines = msg.split("\n")
    assert lines[0] == '*"Tip of the Fatberg"*'
    assert "*Daily MIDI*" in lines[1]


def test_without_song_title():
    params = {
        "scale": "Minor", "root": "A", "tempo": 90,
        "description": "test", "melody_instrument": 0,
        "chord_instrument": 19, "temperature": 1.0,
        "chords": ["Am", "Dm", "Em", "Am"],
    }
    instruments = {
        "melody": [{"program": 0, "name": "Piano"}],
        "chords": [{"program": 19, "name": "Church Organ"}],
    }
    msg = format_message(params, instruments)
    lines = msg.split("\n")
    assert "*Daily MIDI*" in lines[0]

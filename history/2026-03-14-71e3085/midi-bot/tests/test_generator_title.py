"""Tests for song-title-based prompt generation."""
from src.generator import build_llm_prompt_from_title


def test_basic():
    template = 'SONG TITLE:\n"{title}"\n\nInspirations:\n{inspirations}\n\nScales:\n{scales}\n\nMelody:\n{melody_instruments}\n\nChords:\n{chord_instruments}'
    result = build_llm_prompt_from_title(
        template=template,
        title="Tip of the Fatberg",
        inspirations=["lo-fi jazz"],
        scales=[{"name": "Major", "origin": "Western", "intervals": [0, 2, 4, 5, 7, 9, 11]}],
        instruments={"melody": [{"program": 0, "name": "Piano"}], "chords": [{"program": 19, "name": "Organ"}]},
    )
    assert '"Tip of the Fatberg"' in result
    assert "lo-fi jazz" in result
    assert "Major" in result


def test_no_inspirations():
    template = '{title}\n{inspirations}\n{scales}\n{melody_instruments}\n{chord_instruments}'
    result = build_llm_prompt_from_title(
        template=template,
        title="test",
        inspirations=[],
        scales=[{"name": "X", "origin": "Y", "intervals": [0, 2, 4]}],
        instruments={"melody": [{"program": 0, "name": "P"}], "chords": [{"program": 1, "name": "Q"}]},
    )
    assert "(none)" in result

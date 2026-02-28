"""Tests for aligner interface."""

from pathlib import Path
from unittest.mock import patch

from glottisdale.align import get_aligner, DefaultAligner
from glottisdale.types import Syllable


def test_get_aligner_default():
    aligner = get_aligner("default")
    assert isinstance(aligner, DefaultAligner)


def test_get_aligner_unknown():
    import pytest
    with pytest.raises(ValueError, match="Unknown aligner"):
        get_aligner("nonexistent")


@patch("glottisdale.align.transcribe")
def test_default_aligner_produces_syllables(mock_transcribe):
    mock_transcribe.return_value = {
        "text": "Hello world",
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
        "language": "en",
    }

    aligner = DefaultAligner(whisper_model="base")
    result = aligner.process(Path("fake.wav"))

    assert result["text"] == "Hello world"
    assert len(result["syllables"]) >= 2  # "hello" has 2 syllables
    assert all(isinstance(s, Syllable) for s in result["syllables"])
    # Check hello's syllables
    hello_syls = [s for s in result["syllables"] if s.word == "Hello"]
    assert len(hello_syls) == 2

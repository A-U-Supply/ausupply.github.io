"""Tests for Whisper transcription wrapper."""

from unittest.mock import MagicMock, patch
from pathlib import Path

from glottisdale.transcribe import transcribe


def _mock_whisper_result():
    """A realistic Whisper result with word timestamps."""
    return {
        "text": " Hello world.",
        "language": "en",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "text": " Hello world.",
                "words": [
                    {"word": " Hello", "start": 0.0, "end": 0.8, "probability": 0.95},
                    {"word": " world", "start": 0.9, "end": 1.5, "probability": 0.92},
                ],
            }
        ],
    }


@patch("glottisdale.transcribe.whisper")
def test_transcribe_returns_words(mock_whisper):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_whisper_result()
    mock_whisper.load_model.return_value = mock_model

    result = transcribe(Path("fake.wav"), model_name="base")

    assert result["text"] == "Hello world."
    assert len(result["words"]) == 2
    assert result["words"][0]["word"] == "Hello"
    assert result["words"][0]["start"] == 0.0
    assert result["words"][0]["end"] == 0.8
    assert result["words"][1]["word"] == "world"


@patch("glottisdale.transcribe.whisper")
def test_transcribe_strips_word_whitespace(mock_whisper):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_whisper_result()
    mock_whisper.load_model.return_value = mock_model

    result = transcribe(Path("fake.wav"))

    # Words should have leading whitespace stripped
    for w in result["words"]:
        assert w["word"] == w["word"].strip()

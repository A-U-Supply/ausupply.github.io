"""Tests for aligner interface."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from glottisdale.align import get_aligner, DefaultAligner, _bfa_available
from glottisdale.types import Syllable


def test_get_aligner_default():
    aligner = get_aligner("default")
    assert isinstance(aligner, DefaultAligner)


def test_get_aligner_unknown():
    with pytest.raises(ValueError, match="Unknown aligner"):
        get_aligner("nonexistent")


def test_get_aligner_auto_falls_back():
    """Auto mode should fall back to DefaultAligner when BFA not installed."""
    with patch("glottisdale.align._bfa_available", return_value=False):
        aligner = get_aligner("auto")
        assert isinstance(aligner, DefaultAligner)


def test_get_aligner_auto_uses_bfa():
    """Auto mode should use BFA when available."""
    mock_bfa_cls = MagicMock()
    with patch("glottisdale.align._bfa_available", return_value=True), \
         patch("glottisdale.align._get_bfa_class", return_value=mock_bfa_cls):
        get_aligner("auto")
        mock_bfa_cls.assert_called_once()


def test_get_aligner_bfa_lazy_import():
    """BFA mode should lazy-import and raise clear error if not installed."""
    # Patch the dict entry to simulate ImportError from lazy import
    original = get_aligner.__module__
    import glottisdale.align as align_mod
    old_factory = align_mod._ALIGNERS["bfa"]
    align_mod._ALIGNERS["bfa"] = lambda: (_ for _ in ()).throw(ImportError("no bfa"))
    try:
        with pytest.raises(ImportError, match="bournemouth-forced-aligner"):
            get_aligner("bfa")
    finally:
        align_mod._ALIGNERS["bfa"] = old_factory


def test_default_aligner_accepts_extra_kwargs():
    """DefaultAligner should accept and ignore extra kwargs (e.g. device)."""
    aligner = DefaultAligner(whisper_model="base", device="cpu")
    assert aligner.whisper_model == "base"


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

"""Tests for BFA aligner backend."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from glottisdale.types import Phoneme, Syllable
from glottisdale.bfa import BFAAligner, _find_pg16_group, _infer_pg16_from_ipa


def _mock_bfa_phoneme(ipa_label, start_ms, end_ms, index, confidence=0.99):
    """Create a mock BFA phoneme timestamp entry."""
    return {
        "phoneme_label": ipa_label,
        "ipa_label": ipa_label,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "confidence": confidence,
        "index": index,
        "target_seq_idx": index,
        "is_estimated": False,
    }


def _mock_bfa_group(pg16, start_ms, end_ms, index):
    """Create a mock BFA group_ts entry."""
    return {
        "pg16": pg16,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "index": index,
        "target_seq_idx": index,
    }


class TestFindPg16Group:
    def test_match_by_index(self):
        ph = {"index": 2, "start_ms": 100, "end_ms": 200}
        groups = [
            {"index": 0, "pg16": "voiced_stops"},
            {"index": 1, "pg16": "front_vowels"},
            {"index": 2, "pg16": "nasals"},
        ]
        assert _find_pg16_group(ph, groups) == "nasals"

    def test_match_by_timing(self):
        ph = {"index": 99, "start_ms": 100, "end_ms": 200, "ipa_label": "n"}
        groups = [
            {"start_ms": 0, "end_ms": 100, "pg16": "voiced_stops"},
            {"start_ms": 100, "end_ms": 200, "pg16": "nasals"},
        ]
        assert _find_pg16_group(ph, groups) == "nasals"

    def test_fallback_to_ipa_inference(self):
        ph = {"index": 99, "start_ms": 999, "end_ms": 1000, "ipa_label": "n"}
        groups = []  # no groups available
        result = _find_pg16_group(ph, groups)
        assert result == "nasals"


class TestInferPg16FromIpa:
    def test_vowels(self):
        assert _infer_pg16_from_ipa("ə") == "vowels"
        assert _infer_pg16_from_ipa("æ") == "vowels"
        assert _infer_pg16_from_ipa("iː") == "vowels"

    def test_diphthongs(self):
        assert _infer_pg16_from_ipa("aɪ") == "diphthongs"
        assert _infer_pg16_from_ipa("oʊ") == "diphthongs"
        assert _infer_pg16_from_ipa("eɪ") == "diphthongs"

    def test_stops(self):
        assert _infer_pg16_from_ipa("p") == "voiced_stops"
        assert _infer_pg16_from_ipa("b") == "voiced_stops"
        assert _infer_pg16_from_ipa("t") == "voiced_stops"

    def test_nasals(self):
        assert _infer_pg16_from_ipa("m") == "nasals"
        assert _infer_pg16_from_ipa("n") == "nasals"
        assert _infer_pg16_from_ipa("ŋ") == "nasals"

    def test_fricatives(self):
        assert _infer_pg16_from_ipa("f") == "voiceless_fricatives"
        assert _infer_pg16_from_ipa("s") == "voiceless_fricatives"

    def test_laterals(self):
        assert _infer_pg16_from_ipa("l") == "laterals"

    def test_rhotics(self):
        assert _infer_pg16_from_ipa("ɹ") == "rhotics"
        assert _infer_pg16_from_ipa("r") == "rhotics"

    def test_glides(self):
        assert _infer_pg16_from_ipa("j") == "glides"
        assert _infer_pg16_from_ipa("w") == "glides"

    def test_empty_is_silence(self):
        assert _infer_pg16_from_ipa("") == "silence"


class TestBFAAlignerProcess:
    @patch("glottisdale.bfa.transcribe")
    def test_full_pipeline(self, mock_transcribe):
        """Test the full BFA aligner pipeline with mocked dependencies."""
        mock_transcribe.return_value = {
            "text": "hello world",
            "words": [
                {"word": "hello", "start": 0.0, "end": 0.4},
                {"word": "world", "start": 0.5, "end": 0.9},
            ],
            "language": "en",
        }

        # Mock the BFA aligner — returns phonemes for full "hello world"
        mock_bfa = MagicMock()
        mock_bfa.process_sentence.return_value = {
            "phoneme_ts": [
                # "hello" phonemes (absolute timestamps in ms)
                _mock_bfa_phoneme("h", 10.0, 50.0, 0),
                _mock_bfa_phoneme("ɛ", 50.0, 150.0, 1),
                _mock_bfa_phoneme("l", 150.0, 230.0, 2),
                _mock_bfa_phoneme("oʊ", 230.0, 380.0, 3),
                # "world" phonemes
                _mock_bfa_phoneme("w", 510.0, 570.0, 4),
                _mock_bfa_phoneme("ɜː", 570.0, 720.0, 5),
                _mock_bfa_phoneme("l", 720.0, 800.0, 6),
                _mock_bfa_phoneme("d", 800.0, 870.0, 7),
            ],
            "group_ts": [
                _mock_bfa_group("voiceless_fricatives", 10.0, 50.0, 0),
                _mock_bfa_group("front_vowels", 50.0, 150.0, 1),
                _mock_bfa_group("laterals", 150.0, 230.0, 2),
                _mock_bfa_group("diphthongs", 230.0, 380.0, 3),
                _mock_bfa_group("glides", 510.0, 570.0, 4),
                _mock_bfa_group("central_vowels", 570.0, 720.0, 5),
                _mock_bfa_group("laterals", 720.0, 800.0, 6),
                _mock_bfa_group("voiced_stops", 800.0, 870.0, 7),
            ],
        }
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner(whisper_model="base", device="cpu")
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))

        assert result["text"] == "hello world"
        assert len(result["words"]) == 2
        syllables = result["syllables"]
        assert len(syllables) >= 2  # "hello" has 2 syllables, "world" has 1
        assert all(isinstance(s, Syllable) for s in syllables)

        # Check timestamps are absolute (from BFA), not proportional
        hello_syls = [s for s in syllables if s.word == "hello"]
        assert len(hello_syls) == 2
        # First syllable starts at 0.01s (10ms from BFA)
        assert hello_syls[0].start == 0.01

        # BFA was called once with full transcript
        mock_bfa.process_sentence.assert_called_once_with(
            text="hello world",
            audio_wav=mock_bfa.load_audio.return_value,
            do_groups=True,
        )

    @patch("glottisdale.bfa.transcribe")
    def test_bfa_failure_graceful(self, mock_transcribe):
        """If BFA fails entirely, return empty syllables (not crash)."""
        mock_transcribe.return_value = {
            "text": "hello",
            "words": [
                {"word": "hello", "start": 0.0, "end": 0.4},
            ],
            "language": "en",
        }

        mock_bfa = MagicMock()
        mock_bfa.process_sentence.side_effect = RuntimeError("BFA crashed")
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner()
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))

        assert result["text"] == "hello"
        assert result["syllables"] == []  # graceful fallback

    @patch("glottisdale.bfa.transcribe")
    def test_empty_transcript(self, mock_transcribe):
        """Empty transcript should return empty syllables."""
        mock_transcribe.return_value = {
            "text": "",
            "words": [],
            "language": "en",
        }

        mock_bfa = MagicMock()
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner()
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))
        assert result["syllables"] == []
        mock_bfa.process_sentence.assert_not_called()

    @patch("glottisdale.bfa.transcribe")
    def test_phonemes_distributed_by_midpoint(self, mock_transcribe):
        """Phonemes should be assigned to words by their midpoint time."""
        mock_transcribe.return_value = {
            "text": "a b",
            "words": [
                {"word": "a", "start": 0.0, "end": 0.2},
                {"word": "b", "start": 0.3, "end": 0.5},
            ],
            "language": "en",
        }

        mock_bfa = MagicMock()
        mock_bfa.process_sentence.return_value = {
            "phoneme_ts": [
                _mock_bfa_phoneme("ə", 50.0, 150.0, 0),   # midpoint=100ms, in word "a"
                _mock_bfa_phoneme("b", 320.0, 480.0, 1),   # midpoint=400ms, in word "b"
            ],
            "group_ts": [
                _mock_bfa_group("central_vowels", 50.0, 150.0, 0),
                _mock_bfa_group("voiced_stops", 320.0, 480.0, 1),
            ],
        }
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner()
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))
        syllables = result["syllables"]
        assert len(syllables) == 2
        assert syllables[0].word == "a"
        assert syllables[1].word == "b"

    @patch("glottisdale.bfa.transcribe")
    def test_bfa_no_phonemes_returned(self, mock_transcribe):
        """If BFA returns empty phoneme list, return empty syllables."""
        mock_transcribe.return_value = {
            "text": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 0.4}],
            "language": "en",
        }

        mock_bfa = MagicMock()
        mock_bfa.process_sentence.return_value = {
            "phoneme_ts": [],
            "group_ts": [],
        }
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner()
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))
        assert result["syllables"] == []

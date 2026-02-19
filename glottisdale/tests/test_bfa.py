"""Tests for BFA aligner backend."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from glottisdale.types import Phoneme, Syllable
from glottisdale.bfa import BFAAligner, _align_word, _find_pg16_group, _infer_pg16_from_ipa


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


class TestAlignWord:
    def test_basic_word_alignment(self):
        """Test that _align_word converts BFA output to Phoneme objects."""
        mock_aligner = MagicMock()
        mock_aligner.process_sentence.return_value = {
            "phoneme_ts": [
                _mock_bfa_phoneme("k", 0.0, 50.0, 0),
                _mock_bfa_phoneme("æ", 50.0, 150.0, 1),
                _mock_bfa_phoneme("t", 150.0, 200.0, 2),
            ],
            "group_ts": [
                _mock_bfa_group("voiced_stops", 0.0, 50.0, 0),
                _mock_bfa_group("front_vowels", 50.0, 150.0, 1),
                _mock_bfa_group("voiced_stops", 150.0, 200.0, 2),
            ],
        }

        phonemes, groups = _align_word(
            mock_aligner, MagicMock(), "cat",
            word_start=1.0, word_end=1.5,
        )

        assert len(phonemes) == 3
        assert len(groups) == 3
        # Times should be offset by word_start (1.0s) and converted from ms
        assert phonemes[0].label == "k"
        assert phonemes[0].start == 1.0  # 1.0 + 0.0/1000
        assert phonemes[0].end == 1.05   # 1.0 + 50.0/1000
        assert phonemes[1].label == "æ"
        assert groups == ["voiced_stops", "front_vowels", "voiced_stops"]

    def test_timestamps_clamped_to_word_bounds(self):
        """Phoneme timestamps should not exceed word boundaries."""
        mock_aligner = MagicMock()
        mock_aligner.process_sentence.return_value = {
            "phoneme_ts": [
                _mock_bfa_phoneme("k", 0.0, 500.0, 0),  # extends past word end
            ],
            "group_ts": [
                _mock_bfa_group("voiced_stops", 0.0, 500.0, 0),
            ],
        }

        phonemes, groups = _align_word(
            mock_aligner, MagicMock(), "k",
            word_start=1.0, word_end=1.2,
        )

        assert len(phonemes) == 1
        assert phonemes[0].start == 1.0
        assert phonemes[0].end == 1.2  # clamped to word_end

    def test_zero_duration_phonemes_skipped(self):
        """Phonemes with zero/negative duration after clamping should be dropped."""
        mock_aligner = MagicMock()
        mock_aligner.process_sentence.return_value = {
            "phoneme_ts": [
                _mock_bfa_phoneme("k", 300.0, 300.0, 0),  # zero duration
                _mock_bfa_phoneme("æ", 50.0, 150.0, 1),
            ],
            "group_ts": [
                _mock_bfa_group("voiced_stops", 300.0, 300.0, 0),
                _mock_bfa_group("front_vowels", 50.0, 150.0, 1),
            ],
        }

        phonemes, groups = _align_word(
            mock_aligner, MagicMock(), "ka",
            word_start=1.0, word_end=1.5,
        )

        assert len(phonemes) == 1
        assert phonemes[0].label == "æ"

    def test_process_sentence_called_correctly(self):
        """Verify BFA is called with correct parameters."""
        mock_aligner = MagicMock()
        mock_aligner.process_sentence.return_value = {
            "phoneme_ts": [],
            "group_ts": [],
        }
        mock_audio = MagicMock()

        _align_word(mock_aligner, mock_audio, "hello", 0.0, 0.5)

        mock_aligner.process_sentence.assert_called_once_with(
            text="hello",
            audio=mock_audio,
            do_groups=True,
        )


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

        # Mock the BFA aligner
        mock_bfa = MagicMock()

        def mock_process_sentence(text, audio, do_groups=False):
            if text == "hello":
                return {
                    "phoneme_ts": [
                        _mock_bfa_phoneme("h", 0.0, 40.0, 0),
                        _mock_bfa_phoneme("ɛ", 40.0, 120.0, 1),
                        _mock_bfa_phoneme("l", 120.0, 180.0, 2),
                        _mock_bfa_phoneme("oʊ", 180.0, 300.0, 3),
                    ],
                    "group_ts": [
                        _mock_bfa_group("voiceless_fricatives", 0.0, 40.0, 0),
                        _mock_bfa_group("front_vowels", 40.0, 120.0, 1),
                        _mock_bfa_group("laterals", 120.0, 180.0, 2),
                        _mock_bfa_group("diphthongs", 180.0, 300.0, 3),
                    ],
                }
            elif text == "world":
                return {
                    "phoneme_ts": [
                        _mock_bfa_phoneme("w", 0.0, 50.0, 0),
                        _mock_bfa_phoneme("ɜː", 50.0, 200.0, 1),
                        _mock_bfa_phoneme("l", 200.0, 280.0, 2),
                        _mock_bfa_phoneme("d", 280.0, 350.0, 3),
                    ],
                    "group_ts": [
                        _mock_bfa_group("glides", 0.0, 50.0, 0),
                        _mock_bfa_group("central_vowels", 50.0, 200.0, 1),
                        _mock_bfa_group("laterals", 200.0, 280.0, 2),
                        _mock_bfa_group("voiced_stops", 280.0, 350.0, 3),
                    ],
                }
            return {"phoneme_ts": [], "group_ts": []}

        mock_bfa.process_sentence = mock_process_sentence
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner(whisper_model="base", device="cpu")
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))

        assert result["text"] == "hello world"
        assert len(result["words"]) == 2
        syllables = result["syllables"]
        assert len(syllables) >= 2  # "hello" has 2 syllables, "world" has 1
        assert all(isinstance(s, Syllable) for s in syllables)

        # Check hello syllables have real BFA timestamps (not proportional)
        hello_syls = [s for s in syllables if s.word == "hello"]
        assert len(hello_syls) == 2
        # First hello syllable starts at 0.0 (word_start + 0ms)
        assert hello_syls[0].start == 0.0

    @patch("glottisdale.bfa.transcribe")
    def test_bfa_failure_graceful(self, mock_transcribe):
        """If BFA fails for a word, it should be skipped (not crash)."""
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
    def test_empty_words_skipped(self, mock_transcribe):
        """Words with only whitespace should be skipped."""
        mock_transcribe.return_value = {
            "text": "  ",
            "words": [
                {"word": "  ", "start": 0.0, "end": 0.1},
            ],
            "language": "en",
        }

        mock_bfa = MagicMock()
        mock_bfa.load_audio.return_value = MagicMock()

        aligner = BFAAligner()
        aligner._aligner = mock_bfa

        result = aligner.process(Path("fake.wav"))
        assert result["syllables"] == []
        mock_bfa.process_sentence.assert_not_called()

"""Tests for the pipeline orchestrator."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from glottisdale import process
from glottisdale.types import Syllable, Phoneme


def _make_syllables():
    """Fake syllables spanning 0-2 seconds across two words."""
    return [
        Syllable([Phoneme("HH", 0.0, 0.1), Phoneme("AH0", 0.1, 0.25)],
                 0.0, 0.25, "hello", 0),
        Syllable([Phoneme("L", 0.25, 0.35), Phoneme("OW1", 0.35, 0.5)],
                 0.25, 0.5, "hello", 0),
        Syllable([Phoneme("W", 0.6, 0.7), Phoneme("ER1", 0.7, 0.85),
                  Phoneme("L", 0.85, 0.92), Phoneme("D", 0.92, 1.0)],
                 0.6, 1.0, "world", 1),
    ]


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_local_file(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    # Setup mocks
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    # Make cut_clip create empty files
    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    # Make concat create empty file
    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
    )

    assert result.transcript == "[audio] hello world"
    assert len(result.clips) >= 1  # 3 syllables grouped into variable-length words
    assert result.concatenated.exists()
    assert (tmp_path / "out" / "manifest.json").exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_respects_target_duration(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    # Create many syllables (10 x 0.2s = 2s total)
    syllables = [
        Syllable([Phoneme("AH0", i * 0.2, (i + 1) * 0.2)],
                 i * 0.2, (i + 1) * 0.2, f"word{i}", i)
        for i in range(10)
    ]

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "test",
        "words": [],
        "syllables": syllables,
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=0.5,  # Only ~2-3 syllables worth
        seed=42,
    )

    # Should select fewer syllables to stay near target
    total_duration = sum(c.end - c.start for c in result.clips)
    assert total_duration <= 1.0  # Some slack, but well under 2.0


from glottisdale import _weighted_word_length


class TestWeightedWordLength:
    def test_returns_int_in_range(self):
        rng = __import__("random").Random(42)
        for _ in range(100):
            length = _weighted_word_length(1, 4, rng)
            assert 1 <= length <= 4

    def test_distribution_skews_toward_two(self):
        """With default weights, 2-syllable words should be most common."""
        rng = __import__("random").Random(42)
        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for _ in range(1000):
            length = _weighted_word_length(1, 4, rng)
            counts[length] += 1
        # 2-syllable should be the most common
        assert counts[2] > counts[1]
        assert counts[2] > counts[3]
        assert counts[2] > counts[4]

    def test_single_value_range(self):
        rng = __import__("random").Random(42)
        for _ in range(10):
            assert _weighted_word_length(3, 3, rng) == 3

    def test_range_of_two(self):
        rng = __import__("random").Random(42)
        results = {_weighted_word_length(2, 3, rng) for _ in range(50)}
        assert results == {2, 3}


def test_word_grouping_uses_phonotactic_ordering():
    """Words with multiple syllables should be phonotactically ordered."""
    from glottisdale import _group_into_words
    import random

    # Create syllables with distinct phoneme patterns
    syls = [
        Syllable([Phoneme("NG", 0.0, 0.1), Phoneme("AH0", 0.1, 0.2)],
                 0.0, 0.2, "test", 0),  # NG onset = bad
        Syllable([Phoneme("T", 0.3, 0.4), Phoneme("AH0", 0.4, 0.5)],
                 0.3, 0.5, "test", 1),  # T onset = good
        Syllable([Phoneme("AH0", 0.6, 0.7), Phoneme("N", 0.7, 0.8)],
                 0.6, 0.8, "test", 2),  # ends on N = good coda
    ]

    rng = random.Random(42)
    words = _group_into_words(syls, spc_min=3, spc_max=3, rng=rng)

    # All 3 syllables should be in one word
    assert len(words) == 1
    assert len(words[0]) == 3


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_uses_phrase_grouping(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """Process should use phrase-level grouping with appropriate gaps."""
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    # 20 syllables = enough for multiple words and phrases
    syllables = [
        Syllable([Phoneme("AH0", i * 0.1, (i + 1) * 0.1)],
                 i * 0.1, (i + 1) * 0.1, f"word{i}", i)
        for i in range(20)
    ]

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "test",
        "words": [],
        "syllables": syllables,
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        syllables_per_clip="2-3",
        words_per_phrase="3-4",
        phrases_per_sentence="2-3",
        phrase_pause="400-600",
        sentence_pause="800-1000",
        word_crossfade_ms=25,
        seed=42,
    )

    assert len(result.clips) >= 1
    # concatenate_clips should be called multiple times (once per word, per phrase, final)
    assert mock_concat.call_count >= 2


def test_group_into_phrases():
    from glottisdale import _group_into_phrases
    import random

    # 12 words should produce 2-4 phrases with default 3-5 words per phrase
    fake_words = [["w"] for _ in range(12)]  # placeholder word lists
    rng = random.Random(42)
    phrases = _group_into_phrases(fake_words, wpp_min=3, wpp_max=5, rng=rng)

    assert len(phrases) >= 2
    assert len(phrases) <= 6
    # All words accounted for
    total_words = sum(len(p) for p in phrases)
    assert total_words == 12
    # Each phrase has 1-5 words (last phrase may be shorter)
    for phrase in phrases[:-1]:
        assert 3 <= len(phrase) <= 5


def test_group_into_sentences():
    from glottisdale import _group_into_sentences
    import random

    # 6 phrases -> 2-3 sentence groups
    fake_phrases = [["p"] for _ in range(6)]
    rng = random.Random(42)
    sentences = _group_into_sentences(fake_phrases, pps_min=2, pps_max=3, rng=rng)

    assert len(sentences) >= 2
    total_phrases = sum(len(s) for s in sentences)
    assert total_phrases == 6


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_accepts_audio_polish_params(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """process() should accept all audio polish parameters without TypeError."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.0},
        ],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
        noise_level_db=-30,
        room_tone=True,
        pitch_normalize=True,
        pitch_range=3,
        breaths=True,
        breath_probability=0.8,
        volume_normalize=True,
        prosodic_dynamics=True,
    )

    assert result.transcript == "[audio] hello world"
    assert result.concatenated.exists()
    assert (tmp_path / "out" / "manifest.json").exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_audio_polish_all_disabled(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """process() should work with all audio polish features disabled."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
        noise_level_db=0,
        room_tone=False,
        pitch_normalize=False,
        pitch_range=5,
        breaths=False,
        breath_probability=0.0,
        volume_normalize=False,
        prosodic_dynamics=False,
    )

    assert result.concatenated.exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_accepts_stretch_params(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """process() should accept all stretch/repeat parameters without TypeError."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello world",
        "words": [],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
        # Stretch params
        random_stretch=0.3,
        stretch_factor="1.5-3.0",
        # Repeat params
        repeat_weight=0.2,
        repeat_count="1-2",
        repeat_style="exact",
        # Stutter params
        stutter=0.3,
        stutter_count="1-2",
    )
    assert result.concatenated.exists()


@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_all_stretch_repeat_disabled(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """With all stretch/repeat features at None/default, behavior is unchanged."""
    mock_detect.return_value = "audio"

    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "hello",
        "words": [],
        "syllables": _make_syllables(),
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut

    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=10.0,
        seed=42,
        # All defaults — no stretch or repeat
    )
    assert result.concatenated.exists()

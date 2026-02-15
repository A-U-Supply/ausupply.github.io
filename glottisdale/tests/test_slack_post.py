"""Tests for Slack posting."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from glottisdale_slack.post import post_results
from glottisdale.types import Result, Clip, Syllable, Phoneme


@patch("glottisdale_slack.post.find_channel_id", return_value="C999")
def test_post_results(mock_find_ch, tmp_path):
    client = MagicMock()
    # files_upload_v2 returns file list with ID
    client.files_upload_v2.return_value = {
        "files": [{"id": "F123"}],
    }
    # files_info returns shares so we can get thread_ts
    client.files_info.return_value = {
        "file": {
            "shares": {
                "public": {
                    "C999": [{"ts": "111.222"}]
                }
            }
        }
    }

    # Create real files so the upload paths exist
    concat_path = tmp_path / "concatenated.wav"
    concat_path.touch()
    zip_path = tmp_path / "clips.zip"
    zip_path.touch()

    result = Result(
        clips=[
            Clip(
                syllables=[Syllable([Phoneme("AH0", 0.0, 0.1)], 0.0, 0.1, "test", 0)],
                start=0.0, end=0.1, source="video1",
                output_path=tmp_path / "clips" / "001_word.wav",
            ),
        ],
        concatenated=concat_path,
        transcript="test",
        manifest={},
    )

    sources = [{"name": "video1.mp4", "permalink": "https://slack.com/archives/C001/p123"}]

    post_results(
        token="xoxb-test",
        channel="#glottisdale",
        result=result,
        sources=sources,
        output_dir=tmp_path,
        _client=client,
    )

    # WAV uploaded as TOP-LEVEL message (no thread_ts)
    audio_upload = client.files_upload_v2.call_args_list[0]
    assert "glottisdale-" in audio_upload[1]["filename"]
    assert audio_upload[1]["filename"].endswith(".wav")
    assert "thread_ts" not in audio_upload[1]

    # Zip uploaded as TOP-LEVEL (no thread_ts)
    zip_upload = client.files_upload_v2.call_args_list[1]
    assert "thread_ts" not in zip_upload[1]

    # Source links in thread
    source_call = client.chat_postMessage.call_args_list[0]
    assert source_call[1]["thread_ts"] == "111.222"
    assert "video1.mp4" in source_call[1]["text"]


@patch("glottisdale_slack.post.find_channel_id", return_value="C999")
def test_wav_upload_failure_crashes(mock_find_ch, tmp_path):
    """WAV upload failure must raise — never silently proceed."""
    client = MagicMock()
    client.files_upload_v2.side_effect = Exception("504 Gateway Timeout")

    concat_path = tmp_path / "concatenated.wav"
    concat_path.touch()

    result = Result(
        clips=[],
        concatenated=concat_path,
        transcript="test",
        manifest={},
    )

    with pytest.raises(Exception, match="504 Gateway Timeout"):
        post_results(
            token="xoxb-test",
            channel="#glottisdale",
            result=result,
            sources=[],
            output_dir=tmp_path,
            _client=client,
        )


@patch("glottisdale_slack.post.find_channel_id", return_value="C999")
def test_missing_wav_raises(mock_find_ch, tmp_path):
    """Missing WAV file must raise FileNotFoundError."""
    client = MagicMock()

    result = Result(
        clips=[],
        concatenated=tmp_path / "nonexistent.wav",
        transcript="test",
        manifest={},
    )

    with pytest.raises(FileNotFoundError):
        post_results(
            token="xoxb-test",
            channel="#glottisdale",
            result=result,
            sources=[],
            output_dir=tmp_path,
            _client=client,
        )

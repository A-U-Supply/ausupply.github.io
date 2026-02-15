"""Tests for Slack posting."""

from pathlib import Path
from unittest.mock import MagicMock, call

from glottisdale_slack.post import post_results
from glottisdale.types import Result, Clip, Syllable, Phoneme


def test_post_results(tmp_path):
    client = MagicMock()
    client.chat_postMessage.return_value = {
        "ts": "111.222",
        "channel": "C999",
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

    # Summary posted as main message first
    summary_call = client.chat_postMessage.call_args_list[0]
    assert "1 words" in summary_call[1]["text"]

    # Audio + zip uploaded in thread
    assert client.files_upload_v2.call_count == 2
    audio_upload = client.files_upload_v2.call_args_list[0]
    assert audio_upload[1]["filename"] == "glottisdale.wav"
    assert audio_upload[1]["thread_ts"] == "111.222"

    zip_upload = client.files_upload_v2.call_args_list[1]
    assert zip_upload[1]["filename"] == "clips.zip"
    assert zip_upload[1]["thread_ts"] == "111.222"

    # Source links in thread
    source_call = client.chat_postMessage.call_args_list[1]
    assert source_call[1]["thread_ts"] == "111.222"
    assert "video1.mp4" in source_call[1]["text"]

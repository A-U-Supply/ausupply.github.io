"""Tests for Slack posting."""

from pathlib import Path
from unittest.mock import MagicMock, call

from glottisdale_slack.post import post_results
from glottisdale.types import Result, Clip, Syllable, Phoneme


def test_post_results(tmp_path):
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

    # Zip uploaded in thread
    zip_upload = client.files_upload_v2.call_args_list[1]
    assert zip_upload[1]["thread_ts"] == "111.222"

    # Source links in thread
    source_call = client.chat_postMessage.call_args_list[0]
    assert source_call[1]["thread_ts"] == "111.222"
    assert "video1.mp4" in source_call[1]["text"]

"""Tests for Slack posting."""

from pathlib import Path
from unittest.mock import MagicMock, call

from glottisdale_slack.post import post_results
from glottisdale.types import Result, Clip, Syllable, Phoneme


def test_post_results():
    client = MagicMock()
    client.chat_postMessage.return_value = {
        "ts": "111.222",
        "channel": "C999",
    }

    result = Result(
        clips=[
            Clip(
                syllables=[Syllable([Phoneme("AH0", 0.0, 0.1)], 0.0, 0.1, "test", 0)],
                start=0.0, end=0.1, source="video1",
                output_path=Path("/tmp/clips/001_video1_w00_s00.ogg"),
            ),
        ],
        concatenated=Path("/tmp/concatenated.ogg"),
        transcript="test",
        manifest={},
    )

    sources = [{"name": "video1.mp4", "permalink": "https://slack.com/archives/C001/p123"}]

    # Mock file existence
    post_results(
        token="xoxb-test",
        channel="#glottisdale",
        result=result,
        sources=sources,
        output_dir=Path("/tmp"),
        _client=client,  # inject mock
    )

    # Should post summary message
    client.chat_postMessage.assert_called_once()
    msg_text = client.chat_postMessage.call_args[1]["text"]
    assert "video1.mp4" in msg_text
    assert "1 syllable clips" in msg_text

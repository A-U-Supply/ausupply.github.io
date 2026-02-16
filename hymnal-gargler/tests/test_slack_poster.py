"""Tests for Slack poster."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from slack_poster import format_message


def test_format_message():
    msg = format_message(
        scale="Hirajoshi",
        root="F#",
        tempo=145,
        description="Bureaucrats dancing in the rain",
        source_link="https://slack.com/archives/C123/p456",
    )
    assert "Hymnal Gargler" in msg
    assert "Hirajoshi" in msg
    assert "F#" in msg
    assert "145 BPM" in msg
    assert "Bureaucrats dancing in the rain" in msg
    assert "https://slack.com/archives/C123/p456" in msg


def test_format_message_no_description():
    msg = format_message("Blues", "A", 120, "", "https://link")
    assert "Hymnal Gargler" in msg
    assert "_" not in msg or "Blues" in msg  # no empty italics

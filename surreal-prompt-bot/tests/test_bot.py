"""Tests for main bot entrypoint."""
from unittest.mock import patch, MagicMock
import os

import pytest


def test_bot_dry_run_does_not_post():
    """Dry run generates prompt but doesn't post to Slack."""
    with patch("bot.scrape_all_sources", return_value=["Test headline"]), \
         patch("bot.load_inspirations", return_value=["test style"]), \
         patch("bot.sample_inspirations", return_value=["test style"]), \
         patch("bot.generate_prompt", return_value="Test prompt"), \
         patch("bot.post_to_slack") as mock_post, \
         patch.dict(os.environ, {"HF_TOKEN": "test"}):

        from bot import run_bot

        class Args:
            dry_run = True
            channel = None
            temperature = None
            sources = None
            no_inspirations = False
            config = "config.yaml"

        result = run_bot(Args())

        mock_post.assert_not_called()
        assert result == 0


def test_bot_posts_on_success():
    """Bot posts generated prompt to Slack."""
    with patch("bot.scrape_all_sources", return_value=["Test headline"]), \
         patch("bot.load_inspirations", return_value=["test style"]), \
         patch("bot.sample_inspirations", return_value=["test style"]), \
         patch("bot.generate_prompt", return_value="Test prompt"), \
         patch("bot.post_to_slack", return_value=True) as mock_post, \
         patch.dict(os.environ, {"HF_TOKEN": "test", "SLACK_BOT_TOKEN": "xoxb-test"}):

        from bot import run_bot

        class Args:
            dry_run = False
            channel = "#test"
            temperature = None
            sources = None
            no_inspirations = False
            config = "config.yaml"

        result = run_bot(Args())

        mock_post.assert_called_once()
        assert result == 0

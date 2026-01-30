"""Tests for config loader."""
import tempfile
from pathlib import Path

import pytest

from src.config import load_config, merge_cli_args


def test_load_config_defaults():
    """Config has sensible defaults when file missing."""
    config = load_config(Path("/nonexistent/config.yaml"))
    assert config["slack"]["channel"] == "#drawma"
    assert config["prompt"]["model"] == "llama-3.1-8b-instant"


def test_load_config_from_file():
    """Config loads values from YAML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("slack:\n  channel: '#test-channel'\n")
        f.flush()
        config = load_config(Path(f.name))
    assert config["slack"]["channel"] == "#test-channel"


def test_merge_cli_args_overrides():
    """CLI args override config values."""
    config = {"slack": {"channel": "#drawma"}, "prompt": {"temperature": 1.0}}

    class Args:
        channel = "#override"
        temperature = 1.5
        sources = None
        no_inspirations = False

    merged = merge_cli_args(config, Args())
    assert merged["slack"]["channel"] == "#override"
    assert merged["prompt"]["temperature"] == 1.5

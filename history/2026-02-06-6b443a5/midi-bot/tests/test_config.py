import pytest
from pathlib import Path
from unittest.mock import patch
from src.config import load_config, merge_cli_args


def test_load_config_defaults(tmp_path):
    """Config loads with defaults when no YAML file exists."""
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config["slack"]["channel"] == "#midieval"
    assert config["prompt"]["model"] == "meta-llama/Llama-3.3-70B-Instruct"
    assert config["prompt"]["temperature"] == 1.0
    assert config["prompt"]["max_headlines"] == 10


def test_load_config_from_yaml(tmp_path):
    """Config loads values from YAML file."""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text('slack:\n  channel: "#test"\nprompt:\n  temperature: 0.5\n')
    config = load_config(yaml_file)
    assert config["slack"]["channel"] == "#test"
    assert config["prompt"]["temperature"] == 0.5
    # Defaults still present for unset keys
    assert config["prompt"]["model"] == "meta-llama/Llama-3.3-70B-Instruct"


def test_merge_cli_args():
    """CLI args override config values."""
    config = {"slack": {"channel": "#midieval"}, "prompt": {"temperature": 1.0},
              "inspirations": {"pick_count": 2}, "sources": ["reuters"]}

    class Args:
        channel = "#override"
        temperature = 0.8
        sources = None
        no_inspirations = False

    result = merge_cli_args(config, Args())
    assert result["slack"]["channel"] == "#override"
    assert result["prompt"]["temperature"] == 0.8

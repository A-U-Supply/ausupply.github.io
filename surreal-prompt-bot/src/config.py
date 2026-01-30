"""Configuration loader with YAML support and CLI overrides."""
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = {
    "slack": {
        "channel": "#drawma",
    },
    "prompt": {
        "temperature": 1.0,
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "max_headlines": 10,
    },
    "inspirations": {
        "file": "inspirations.txt",
        "pick_count": 2,
    },
    "sources": [
        "reuters", "foxnews", "cnn", "bbc",
        "ft", "bloomberg", "guardian", "breitbart"
    ],
}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load config from YAML file, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()

    if config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_cli_args(config: dict[str, Any], args) -> dict[str, Any]:
    """Merge CLI arguments into config, overriding where specified."""
    if args.channel:
        config["slack"]["channel"] = args.channel
    if args.temperature is not None:
        config["prompt"]["temperature"] = args.temperature
    if args.sources:
        config["sources"] = args.sources.split(",")
    if args.no_inspirations:
        config["inspirations"]["pick_count"] = 0
    return config

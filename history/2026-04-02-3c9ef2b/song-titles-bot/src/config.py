"""Configuration loader."""
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "channel": "song-titles",
    "model": "meta-llama/Llama-3.3-70B-Instruct",
    "titles_path": "titles.json",
    "html_output_path": "../this-song-is-a-junkyard.html",
}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load config from YAML, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config.update(file_config)
    return config

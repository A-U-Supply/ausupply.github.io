import json
from pathlib import Path


def save_titles(titles: list[str], cache_path: Path) -> None:
    """Save filtered titles to JSON cache."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(titles, indent=2))


def load_titles(cache_path: Path) -> list[str]:
    """Load titles from JSON cache. Returns empty list if not found."""
    if not cache_path.exists():
        return []
    return json.loads(cache_path.read_text())

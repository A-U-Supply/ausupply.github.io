"""Select random unused song titles with usage tracking."""
import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


def load_titles(titles_path: Path) -> list[dict]:
    """Load titles from JSON file. Returns empty list if missing."""
    if not titles_path.exists():
        logger.warning(f"Titles file not found: {titles_path}")
        return []
    return json.loads(titles_path.read_text())


def select_title(titles_path: Path, used_path: Path) -> dict | None:
    """Pick a random unused title, record usage, return title dict.

    When all titles have been used, resets the used list and picks fresh.
    Returns None if titles file is empty or missing.
    """
    titles = load_titles(titles_path)
    if not titles:
        return None

    if used_path.exists():
        used_data = json.loads(used_path.read_text())
    else:
        used_data = {"used_ids": []}

    used_ids = set(used_data["used_ids"])
    all_ids = {t["id"] for t in titles}

    unused = [t for t in titles if t["id"] not in used_ids]

    if not unused:
        logger.info(f"All {len(titles)} titles used, resetting pool")
        used_ids = set()
        unused = titles

    title = random.choice(unused)
    used_ids.add(title["id"])

    used_data["used_ids"] = sorted(used_ids & all_ids)
    used_path.write_text(json.dumps(used_data, indent=2) + "\n")

    logger.info(f"Selected title: \"{title['title']}\" ({len(used_data['used_ids'])}/{len(titles)} used)")
    return title

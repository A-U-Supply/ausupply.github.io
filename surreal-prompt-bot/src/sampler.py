"""Inspiration sampler - picks random artistic inspirations from text file."""
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


def load_inspirations(file_path: Path) -> list[str]:
    """Load inspirations from text file, one per line."""
    if not file_path.exists():
        logger.warning(f"Inspirations file not found: {file_path}")
        return []

    with open(file_path) as f:
        lines = [line.strip() for line in f if line.strip()]

    logger.info(f"Loaded {len(lines)} inspirations from {file_path}")
    return lines


def sample_inspirations(inspirations: list[str], count: int) -> list[str]:
    """Randomly sample N inspirations from list."""
    if count <= 0:
        return []

    if len(inspirations) <= count:
        return inspirations[:]

    return random.sample(inspirations, count)

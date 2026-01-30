"""Tests for inspiration sampler."""
import tempfile
from pathlib import Path

import pytest

from src.sampler import load_inspirations, sample_inspirations


def test_load_inspirations_from_file():
    """Loads lines from text file, strips whitespace."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line one\n  line two  \n\nline three\n")
        f.flush()
        inspirations = load_inspirations(Path(f.name))

    assert inspirations == ["line one", "line two", "line three"]


def test_load_inspirations_missing_file():
    """Returns empty list for missing file."""
    inspirations = load_inspirations(Path("/nonexistent/file.txt"))
    assert inspirations == []


def test_sample_inspirations_picks_n():
    """Samples requested number of items."""
    items = ["a", "b", "c", "d", "e"]
    sampled = sample_inspirations(items, count=2)
    assert len(sampled) == 2
    assert all(s in items for s in sampled)


def test_sample_inspirations_handles_small_list():
    """Returns all items if fewer than requested."""
    items = ["a", "b"]
    sampled = sample_inspirations(items, count=5)
    assert len(sampled) == 2


def test_sample_inspirations_zero_count():
    """Returns empty list for zero count."""
    sampled = sample_inspirations(["a", "b", "c"], count=0)
    assert sampled == []

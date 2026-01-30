# tests/test_generator.py
import pytest
import random

from src.generator import (
    generate_chaos_styles,
    GeneratorConfig,
    NEON_PALETTE,
    FONTS,
)


def test_generate_chaos_styles_deterministic_with_seed():
    """Same seed should produce same styles."""
    config = GeneratorConfig(seed=42)
    titles = ["Title A", "Title B", "Title C"]

    styles1 = generate_chaos_styles(titles, config)
    styles2 = generate_chaos_styles(titles, config)

    assert styles1 == styles2


def test_generate_chaos_styles_respects_max_rotation():
    """Rotation should not exceed max_rotation."""
    config = GeneratorConfig(seed=42, max_rotation=15)
    titles = ["Title"] * 50

    styles = generate_chaos_styles(titles, config)

    for style in styles:
        assert -15 <= style["rotation"] <= 15


def test_generate_chaos_styles_uses_palette():
    """Colors should come from specified palette."""
    config = GeneratorConfig(seed=42, color_palette="neon")
    titles = ["Title"] * 20

    styles = generate_chaos_styles(titles, config)

    for style in styles:
        assert style["color"] in NEON_PALETTE

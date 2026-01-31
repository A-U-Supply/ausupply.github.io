"""Tests for prompt generator."""
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

import pytest

from src.generator import generate_prompt, build_llm_prompt, load_template


def test_build_llm_prompt_includes_headlines():
    """LLM prompt contains all headlines."""
    template = "Headlines:\n{headlines}\n\nInspirations:\n{inspirations}"
    headlines = ["Economy crashes", "Aliens land"]
    inspirations = ["vaporwave"]

    prompt = build_llm_prompt(template, headlines, inspirations)

    assert "Economy crashes" in prompt
    assert "Aliens land" in prompt
    assert "vaporwave" in prompt


def test_build_llm_prompt_without_inspirations():
    """LLM prompt works without inspirations."""
    template = "Headlines:\n{headlines}\n\nInspirations:\n{inspirations}"
    headlines = ["Breaking news"]

    prompt = build_llm_prompt(template, headlines, [])

    assert "Breaking news" in prompt
    assert "(none)" in prompt


def test_load_template_splits_on_separator():
    """Template file splits on --- separator."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("System prompt here\n---\nUser template here")
        f.flush()
        system, user = load_template(Path(f.name))

    assert system == "System prompt here"
    assert user == "User template here"


def test_generate_prompt_calls_huggingface():
    """Generator calls Hugging Face API and returns response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test prompt output"))]
    mock_client.chat_completion.return_value = mock_response

    # Create a temp template file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Be creative\n---\nHeadlines:\n{headlines}\n\nStyle:\n{inspirations}")
        f.flush()
        template_path = Path(f.name)

    with patch("src.generator.InferenceClient", return_value=mock_client):
        result = generate_prompt(
            headlines=["Test headline"],
            inspirations=["test style"],
            model="HuggingFaceTB/SmolLM3-3B",
            temperature=1.0,
            api_key="test-key",
            template_path=template_path
        )

    assert result == "Test prompt output"
    mock_client.chat_completion.assert_called_once()

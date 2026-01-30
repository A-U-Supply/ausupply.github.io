"""Tests for prompt generator."""
from unittest.mock import patch, MagicMock

import pytest

from src.generator import generate_prompt, build_llm_prompt


def test_build_llm_prompt_includes_headlines():
    """LLM prompt contains all headlines."""
    headlines = ["Economy crashes", "Aliens land"]
    inspirations = ["vaporwave"]

    prompt = build_llm_prompt(headlines, inspirations)

    assert "Economy crashes" in prompt
    assert "Aliens land" in prompt
    assert "vaporwave" in prompt


def test_build_llm_prompt_without_inspirations():
    """LLM prompt works without inspirations."""
    headlines = ["Breaking news"]

    prompt = build_llm_prompt(headlines, [])

    assert "Breaking news" in prompt
    assert "Artistic inspiration" not in prompt


def test_generate_prompt_calls_groq():
    """Generator calls Groq API and returns response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test prompt output"))]
    mock_client.chat.completions.create.return_value = mock_response

    with patch("src.generator.Groq", return_value=mock_client):
        result = generate_prompt(
            headlines=["Test headline"],
            inspirations=["test style"],
            model="llama-3.1-8b-instant",
            temperature=1.0,
            api_key="test-key"
        )

    assert result == "Test prompt output"
    mock_client.chat.completions.create.assert_called_once()

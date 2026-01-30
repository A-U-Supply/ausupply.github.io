"""Prompt generator using Groq API."""
import logging

from groq import Groq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a surrealist artist with severe internet brain rot.
Generate a single drawing prompt in the style of a surreal, unhinged headline.
Include 1-3 emojis. One sentence. Do not explain it."""


def build_llm_prompt(headlines: list[str], inspirations: list[str]) -> str:
    """Build the prompt to send to the LLM."""
    parts = ["Today's news headlines:"]
    for headline in headlines:
        parts.append(f"- {headline}")

    if inspirations:
        parts.append("\nArtistic inspiration for today:")
        for insp in inspirations:
            parts.append(f"- {insp}")

    return "\n".join(parts)


def generate_prompt(
    headlines: list[str],
    inspirations: list[str],
    model: str,
    temperature: float,
    api_key: str,
) -> str:
    """Generate a surreal prompt using Groq API."""
    client = Groq(api_key=api_key)

    user_prompt = build_llm_prompt(headlines, inspirations)
    logger.debug(f"LLM prompt:\n{user_prompt}")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=150,
    )

    result = response.choices[0].message.content.strip()
    logger.info(f"Generated prompt: {result}")
    return result

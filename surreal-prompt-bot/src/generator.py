"""Prompt generator using Hugging Face Inference API."""
import logging
import re

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a surrealist artist with severe internet brain rot.
Generate a single drawing prompt in the style of a surreal, unhinged headline.
Include 1-3 emojis. One sentence. Do not explain it. Do not think out loud. Just output the headline directly.
Do NOT use all caps. Use normal sentence case. You may use Slack formatting like *bold* or _italics_ if it adds flair."""


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
    """Generate a surreal prompt using Hugging Face Inference API."""
    client = InferenceClient(token=api_key)

    user_prompt = build_llm_prompt(headlines, inspirations)
    logger.debug(f"LLM prompt:\n{user_prompt}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat_completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=1000,
    )

    result = response.choices[0].message.content.strip()

    # Strip thinking tags if present (some models output <think>...</think>)
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
    # Also handle unclosed think tags
    result = re.sub(r'<think>.*', '', result, flags=re.DOTALL).strip()

    # Convert standard markdown to Slack mrkdwn format
    # **bold** -> *bold*
    result = re.sub(r'\*\*(.+?)\*\*', r'*\1*', result)
    # __bold__ -> *bold*
    result = re.sub(r'__(.+?)__', r'*\1*', result)
    # *italic* -> _italic_ (but not if already *bold*)
    # Only convert single * that aren't part of **
    result = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', result)

    logger.info(f"Generated prompt: {result}")
    return result

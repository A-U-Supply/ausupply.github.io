"""Prompt generator using Hugging Face Inference API."""
import logging
import re
from pathlib import Path

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


def load_template(template_path: Path) -> tuple[str, str]:
    """Load prompt template from file. Returns (system_prompt, user_template)."""
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    content = template_path.read_text()
    parts = content.split("---", 1)

    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    else:
        # No separator, treat whole thing as user template
        return "", content.strip()


def build_llm_prompt(template: str, headlines: list[str], inspirations: list[str]) -> str:
    """Build the prompt using template with placeholders."""
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    inspirations_text = "\n".join(f"- {i}" for i in inspirations) if inspirations else "(none)"

    return template.format(
        headlines=headlines_text,
        inspirations=inspirations_text
    )


def generate_prompt(
    headlines: list[str],
    inspirations: list[str],
    model: str,
    temperature: float,
    api_key: str,
    template_path: Path = None,
) -> str:
    """Generate a surreal prompt using Hugging Face Inference API."""
    client = InferenceClient(token=api_key)

    # Load template
    if template_path is None:
        template_path = Path(__file__).parent.parent / "prompt_template.txt"

    system_prompt, user_template = load_template(template_path)
    user_prompt = build_llm_prompt(user_template, headlines, inspirations)

    logger.debug(f"System prompt:\n{system_prompt}")
    logger.debug(f"User prompt:\n{user_prompt}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

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
    result = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', result)

    logger.info(f"Generated prompt: {result}")
    return result

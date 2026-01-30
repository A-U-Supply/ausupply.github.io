# src/filter.py
from dataclasses import dataclass

import requests


@dataclass
class FilterConfig:
    model: str = "llama3"
    base_url: str = "http://localhost:11434"


CLASSIFICATION_PROMPT = """Is this message a potential song title for a band?
Not discussion about titles - the title itself.
Reply only YES or NO.

Message: "{message}"
"""


def classify_message(message: str, config: FilterConfig) -> bool:
    """Ask Ollama if a message is a song title."""
    prompt = CLASSIFICATION_PROMPT.format(message=message)

    response = requests.post(
        f"{config.base_url}/api/generate",
        json={
            "model": config.model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    answer = response.json().get("response", "").strip().upper()
    return answer.startswith("YES")


def filter_song_titles(messages: list[str], config: FilterConfig) -> list[str]:
    """Filter a list of messages to only those classified as song titles."""
    return [msg for msg in messages if classify_message(msg, config)]

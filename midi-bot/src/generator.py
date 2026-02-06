"""Music parameter generator using Hugging Face Inference API."""
import json
import logging
import re
from pathlib import Path
from typing import Any

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


def load_scales(scales_path: Path) -> list[dict]:
    """Load scales database from JSON file."""
    return json.loads(scales_path.read_text())


def load_instruments(instruments_path: Path) -> dict[str, list[dict]]:
    """Load instruments database from JSON file."""
    return json.loads(instruments_path.read_text())


def load_template(template_path: Path) -> tuple[str, str]:
    """Load prompt template. Returns (system_prompt, user_template)."""
    content = template_path.read_text()
    parts = content.split("---", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", content.strip()


def build_llm_prompt(
    template: str,
    headlines: list[str],
    inspirations: list[str],
    scales: list[dict],
    instruments: dict[str, list[dict]],
) -> str:
    """Build the prompt with all context injected."""
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    inspirations_text = "\n".join(f"- {i}" for i in inspirations) if inspirations else "(none)"
    scales_text = "\n".join(f"- {s['name']} ({s['origin']})" for s in scales)
    melody_text = "\n".join(f"- {i['program']}: {i['name']}" for i in instruments["melody"])
    chords_text = "\n".join(f"- {i['program']}: {i['name']}" for i in instruments["chords"])

    return template.format(
        headlines=headlines_text,
        inspirations=inspirations_text,
        scales=scales_text,
        melody_instruments=melody_text,
        chord_instruments=chords_text,
    )


def parse_llm_response(response: str) -> dict[str, Any]:
    """Parse the LLM's JSON response, handling code fences and think tags."""
    # Strip think tags
    cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL).strip()
    # Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response[:200]}")


def validate_params(
    params: dict[str, Any],
    scales: list[dict],
    instruments: dict[str, list[dict]],
) -> None:
    """Validate LLM-generated params. Raises ValueError on invalid params."""
    scale_names = {s["name"] for s in scales}
    if params.get("scale") not in scale_names:
        raise ValueError(f"Unknown scale: {params.get('scale')}")

    tempo = params.get("tempo", 0)
    if not (40 <= tempo <= 200):
        raise ValueError(f"Invalid tempo: {tempo} (must be 40-200)")

    temp = params.get("temperature", 0)
    if not (0.5 <= temp <= 1.5):
        raise ValueError(f"Invalid temperature: {temp} (must be 0.5-1.5)")

    valid_melody = {i["program"] for i in instruments["melody"]}
    if params.get("melody_instrument") not in valid_melody:
        raise ValueError(f"Invalid melody_instrument: {params.get('melody_instrument')}")

    valid_chords = {i["program"] for i in instruments["chords"]}
    if params.get("chord_instrument") not in valid_chords:
        raise ValueError(f"Invalid chord_instrument: {params.get('chord_instrument')}")

    if not isinstance(params.get("chords"), list) or len(params["chords"]) != 4:
        raise ValueError(f"chords must be an array of exactly 4 chord symbols")


def generate_music_params(
    headlines: list[str],
    inspirations: list[str],
    scales: list[dict],
    instruments: dict[str, list[dict]],
    model: str,
    temperature: float,
    api_key: str,
    template_path: Path = None,
) -> dict[str, Any]:
    """Generate structured music parameters via LLM."""
    client = InferenceClient(token=api_key)

    if template_path is None:
        template_path = Path(__file__).parent.parent / "prompt_template.txt"

    system_prompt, user_template = load_template(template_path)
    user_prompt = build_llm_prompt(user_template, headlines, inspirations, scales, instruments)

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

    result_text = response.choices[0].message.content.strip()
    logger.info(f"LLM response: {result_text[:200]}")

    params = parse_llm_response(result_text)
    validate_params(params, scales, instruments)

    return params

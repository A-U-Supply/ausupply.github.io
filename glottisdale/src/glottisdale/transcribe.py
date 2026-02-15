"""Whisper ASR transcription with word-level timestamps."""

from pathlib import Path

import whisper

_model_cache: dict[str, object] = {}


def transcribe(
    audio_path: Path,
    model_name: str = "base",
    language: str = "en",
) -> dict:
    """Transcribe audio and return word-level timestamps.

    Returns:
        Dict with keys:
            text: Full transcript (stripped)
            words: List of dicts with 'word', 'start', 'end' keys
            language: Detected or specified language
    """
    if model_name not in _model_cache:
        _model_cache[model_name] = whisper.load_model(model_name)
    model = _model_cache[model_name]

    result = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language=language,
    )

    # Flatten words across segments, strip whitespace
    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
            })

    return {
        "text": result["text"].strip(),
        "words": words,
        "language": result.get("language", language),
    }

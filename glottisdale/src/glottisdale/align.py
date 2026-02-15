"""Aligner interface and backends."""

from abc import ABC, abstractmethod
from pathlib import Path

from glottisdale.types import Syllable
from glottisdale.transcribe import transcribe
from glottisdale.syllabify import syllabify_words


class Aligner(ABC):
    """Abstract base for speech alignment backends."""

    @abstractmethod
    def process(self, audio_path: Path) -> dict:
        """Transcribe and align audio, returning syllable-level timestamps.

        Returns:
            Dict with keys:
                text: Full transcript
                words: List of word dicts with timestamps
                syllables: List of Syllable objects
        """


class DefaultAligner(Aligner):
    """Whisper ASR + g2p_en + ARPABET syllabifier.

    Word-level timestamps from Whisper, phoneme conversion via g2p_en,
    syllable timing estimated by proportional distribution.
    """

    def __init__(self, whisper_model: str = "base", language: str = "en"):
        self.whisper_model = whisper_model
        self.language = language

    def process(self, audio_path: Path) -> dict:
        result = transcribe(audio_path, model_name=self.whisper_model, language=self.language)
        syllables = syllabify_words(result["words"])
        return {
            "text": result["text"],
            "words": result["words"],
            "syllables": syllables,
        }


# Registry of available backends
_ALIGNERS = {
    "default": DefaultAligner,
}


def get_aligner(name: str, **kwargs) -> Aligner:
    """Get an aligner backend by name."""
    if name not in _ALIGNERS:
        raise ValueError(f"Unknown aligner: {name!r}. Available: {list(_ALIGNERS.keys())}")
    return _ALIGNERS[name](**kwargs)

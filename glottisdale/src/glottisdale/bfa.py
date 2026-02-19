"""BFA (Bournemouth Forced Aligner) backend for phoneme-level alignment."""

import logging
from pathlib import Path

from glottisdale.align import Aligner
from glottisdale.transcribe import transcribe
from glottisdale.types import Phoneme, Syllable
from glottisdale.syllabify_ipa import syllabify_ipa

logger = logging.getLogger(__name__)


class BFAAligner(Aligner):
    """BFA phoneme-level forced aligner.

    Uses Whisper for transcription (word-level timestamps), then BFA
    for precise phoneme-level timestamps with pg16 group classifications.
    Syllabification uses the IPA sonority-based syllabifier.
    """

    def __init__(
        self,
        whisper_model: str = "base",
        language: str = "en",
        device: str = "cpu",
    ):
        self.whisper_model = whisper_model
        self.language = language
        self.device = device
        self._aligner = None

    def _get_aligner(self):
        """Lazy-init BFA aligner."""
        if self._aligner is None:
            from bournemouth_aligner import PhonemeTimestampAligner

            self._aligner = PhonemeTimestampAligner(
                preset="en-us",
                device=self.device,
            )
        return self._aligner

    def process(self, audio_path: Path) -> dict:
        """Transcribe and align audio using Whisper + BFA.

        Returns:
            Dict with keys:
                text: Full transcript
                words: List of word dicts with timestamps
                syllables: List of Syllable objects with real BFA timestamps
        """
        # Step 1: Whisper transcription for word boundaries
        whisper_result = transcribe(
            audio_path, model_name=self.whisper_model, language=self.language
        )

        # Step 2: BFA phoneme alignment
        aligner = self._get_aligner()
        audio_wav = aligner.load_audio(str(audio_path))

        all_syllables = []
        for word_idx, word_info in enumerate(whisper_result["words"]):
            word_text = word_info["word"].strip()
            if not word_text:
                continue

            try:
                phonemes, pg16_groups = _align_word(
                    aligner, audio_wav, word_text,
                    word_info["start"], word_info["end"],
                )
            except Exception as e:
                logger.debug(f"BFA failed for word '{word_text}': {e}")
                continue

            if not phonemes:
                continue

            syls = syllabify_ipa(
                phonemes=phonemes,
                pg16_groups=pg16_groups,
                word=word_text,
                word_index=word_idx,
            )
            all_syllables.extend(syls)

        return {
            "text": whisper_result["text"],
            "words": whisper_result["words"],
            "syllables": all_syllables,
        }


def _align_word(
    aligner,
    audio_wav,
    word_text: str,
    word_start: float,
    word_end: float,
) -> tuple[list[Phoneme], list[str]]:
    """Run BFA alignment on a single word, returning Phoneme objects + pg16 groups.

    Args:
        aligner: PhonemeTimestampAligner instance.
        audio_wav: Pre-loaded audio from aligner.load_audio().
        word_text: The word to align.
        word_start: Word start time from Whisper (seconds).
        word_end: Word end time from Whisper (seconds).

    Returns:
        Tuple of (phoneme list, pg16 group list), parallel arrays.
    """
    result = aligner.process_sentence(
        text=word_text,
        audio=audio_wav,
        do_groups=True,
    )

    phoneme_ts = result.get("phoneme_ts", [])
    group_ts = result.get("group_ts", [])

    phonemes = []
    pg16_groups = []

    for ph_info in phoneme_ts:
        ipa_label = ph_info.get("ipa_label", ph_info.get("phoneme_label", ""))
        start_ms = ph_info.get("start_ms", 0.0)
        end_ms = ph_info.get("end_ms", 0.0)

        # Convert ms to seconds, offset by word start
        start_s = word_start + start_ms / 1000.0
        end_s = word_start + end_ms / 1000.0

        # Clamp to word boundaries
        start_s = max(start_s, word_start)
        end_s = min(end_s, word_end)

        if end_s <= start_s:
            continue

        phonemes.append(Phoneme(
            label=ipa_label,
            start=round(start_s, 4),
            end=round(end_s, 4),
        ))

        # Find pg16 group for this phoneme
        pg16 = _find_pg16_group(ph_info, group_ts)
        pg16_groups.append(pg16)

    return phonemes, pg16_groups


def _find_pg16_group(ph_info: dict, group_ts: list[dict]) -> str:
    """Find the pg16 group classification for a phoneme.

    BFA provides group_ts with timing and group labels. Match by
    phoneme index or overlapping timing.
    """
    ph_idx = ph_info.get("index", ph_info.get("target_seq_idx", -1))

    # Try matching by index in group_ts
    for group in group_ts:
        if group.get("index") == ph_idx or group.get("target_seq_idx") == ph_idx:
            return group.get("pg16", group.get("group", "consonants"))

    # Fallback: try matching by timing overlap
    ph_start = ph_info.get("start_ms", 0)
    ph_end = ph_info.get("end_ms", 0)
    for group in group_ts:
        g_start = group.get("start_ms", 0)
        g_end = group.get("end_ms", 0)
        if g_start <= ph_start and g_end >= ph_end:
            return group.get("pg16", group.get("group", "consonants"))

    # Last resort: infer from IPA label
    return _infer_pg16_from_ipa(ph_info.get("ipa_label", ""))


def _infer_pg16_from_ipa(ipa_label: str) -> str:
    """Best-effort pg16 group inference from IPA label when BFA groups unavailable."""
    if not ipa_label:
        return "silence"

    # Common vowel IPA symbols
    vowels = set("aeiouɪɛæɑɒɔʊəɜɐʌ")
    diphthong_starts = {"aɪ", "aʊ", "eɪ", "oʊ", "ɔɪ"}

    if any(ipa_label.startswith(d) for d in diphthong_starts):
        return "diphthongs"
    if ipa_label[0] in vowels or ipa_label.rstrip("ːˑ") in vowels:
        return "vowels"

    # Common consonant groups
    stops = set("pbtdkgʔ")
    nasals = set("mnɲŋɴ")
    fricatives = set("fvθðszʃʒçxɣhɦ")
    laterals = set("lɫɬɮ")
    rhotics = {"r", "ɹ", "ɾ", "ɽ", "ʁ", "ʀ"}
    glides = {"j", "w", "ɥ"}

    ch = ipa_label[0]
    if ipa_label in rhotics or ch in {"ɹ", "ɾ", "r"}:
        return "rhotics"
    if ch in stops:
        return "voiced_stops"
    if ch in nasals:
        return "nasals"
    if ch in fricatives:
        return "voiceless_fricatives"
    if ch in laterals:
        return "laterals"
    if ch in glides or ipa_label in glides:
        return "glides"

    return "consonants"

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

    # BFA's default duration_max is 10s; keep chunks under that
    MAX_CHUNK_DURATION = 8.0
    SAMPLE_RATE = 16000  # BFA resamples to 16kHz

    def process(self, audio_path: Path) -> dict:
        """Transcribe and align audio using Whisper + BFA.

        Chunks the Whisper transcript into segments that fit within BFA's
        duration limit, aligns each chunk separately, then merges results.

        Returns:
            Dict with keys:
                text: Full transcript
                words: List of word dicts with timestamps
                syllables: List of Syllable objects with real BFA timestamps
        """
        # Step 1: Whisper transcription for text + word boundaries
        whisper_result = transcribe(
            audio_path, model_name=self.whisper_model, language=self.language
        )

        words = whisper_result["words"]
        if not whisper_result["text"].strip() or not words:
            return {
                "text": whisper_result["text"],
                "words": words,
                "syllables": [],
            }

        # Step 2: Load audio and chunk words into BFA-sized segments
        aligner = self._get_aligner()
        audio_wav = aligner.load_audio(str(audio_path))

        chunks = self._chunk_words(words)
        logger.info(f"Split {len(words)} words into {len(chunks)} BFA chunks")

        # Step 3: Align each chunk, collect phonemes with absolute timestamps
        all_phonemes = []
        all_pg16 = []
        for chunk in chunks:
            chunk_text = " ".join(w["word"].strip() for w in chunk)
            chunk_start = chunk[0]["start"]
            chunk_end = chunk[-1]["end"]

            # Slice audio tensor (add 0.2s padding on each side)
            pad = 0.2
            slice_start = max(0.0, chunk_start - pad)
            slice_end = chunk_end + pad
            start_sample = int(slice_start * self.SAMPLE_RATE)
            end_sample = min(int(slice_end * self.SAMPLE_RATE), audio_wav.shape[1])
            chunk_audio = audio_wav[:, start_sample:end_sample]

            if chunk_audio.shape[1] == 0:
                continue

            try:
                bfa_result = aligner.process_sentence(
                    text=chunk_text,
                    audio_wav=chunk_audio,
                    do_groups=True,
                )
            except Exception as e:
                logger.warning(
                    f"BFA chunk failed ({len(chunk)} words, "
                    f"{chunk_end - chunk_start:.1f}s): {e}"
                )
                continue

            phoneme_ts = bfa_result.get("phoneme_ts", [])
            group_ts = bfa_result.get("group_ts", [])

            for ph_info in phoneme_ts:
                ipa_label = ph_info.get(
                    "ipa_label", ph_info.get("phoneme_label", "")
                )
                start_ms = ph_info.get("start_ms", 0.0)
                end_ms = ph_info.get("end_ms", 0.0)
                # BFA timestamps are relative to chunk — offset to absolute
                abs_start = start_ms / 1000.0 + slice_start
                abs_end = end_ms / 1000.0 + slice_start

                if abs_end <= abs_start or not ipa_label:
                    continue

                all_phonemes.append(Phoneme(
                    label=ipa_label,
                    start=round(abs_start, 4),
                    end=round(abs_end, 4),
                ))
                pg16 = _find_pg16_group(ph_info, group_ts)
                all_pg16.append(pg16)

        if not all_phonemes:
            logger.warning("BFA returned no phonemes across all chunks")
            return {
                "text": whisper_result["text"],
                "words": words,
                "syllables": [],
            }

        logger.info(
            f"BFA aligned {len(all_phonemes)} phonemes across "
            f"{len(words)} words"
        )

        # Step 4: Distribute phonemes to words using Whisper word boundaries
        all_syllables = []
        for word_idx, word_info in enumerate(words):
            word_text = word_info["word"].strip()
            if not word_text:
                continue

            word_start = word_info["start"]
            word_end = word_info["end"]

            # Find phonemes whose midpoint falls within this word's boundaries
            word_phonemes = []
            word_groups = []
            for ph, pg in zip(all_phonemes, all_pg16):
                if pg == "silence":
                    continue
                ph_mid = (ph.start + ph.end) / 2
                if word_start <= ph_mid <= word_end:
                    word_phonemes.append(ph)
                    word_groups.append(pg)

            if not word_phonemes:
                continue

            try:
                syls = syllabify_ipa(
                    phonemes=word_phonemes,
                    pg16_groups=word_groups,
                    word=word_text,
                    word_index=word_idx,
                )
                all_syllables.extend(syls)
            except Exception as e:
                logger.debug(f"Syllabification failed for '{word_text}': {e}")

        return {
            "text": whisper_result["text"],
            "words": words,
            "syllables": all_syllables,
        }

    @classmethod
    def _chunk_words(cls, words: list[dict]) -> list[list[dict]]:
        """Group words into chunks that fit within BFA's duration limit."""
        chunks = []
        current_chunk = []
        chunk_start = None

        for word in words:
            w_start = word["start"]
            w_end = word["end"]

            if chunk_start is None:
                chunk_start = w_start

            if w_end - chunk_start > cls.MAX_CHUNK_DURATION and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [word]
                chunk_start = w_start
            else:
                current_chunk.append(word)

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


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

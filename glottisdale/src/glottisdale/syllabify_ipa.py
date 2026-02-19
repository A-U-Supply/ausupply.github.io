"""IPA sonority-based syllabifier for BFA phoneme output.

Uses BFA's pg16 phoneme group classifications to determine sonority,
then applies Maximum Onset Principle to find syllable boundaries.
"""

from glottisdale.types import Phoneme, Syllable


# Map BFA pg16 groups to sonority levels (higher = more sonorous)
_PG16_SONORITY = {
    "voiced_stops": 0,
    "voiceless_stops": 0,  # not in pg16 but handle if seen
    "affricates": 1,
    "voiceless_fricatives": 2,
    "voiced_fricatives": 2,
    "nasals": 3,
    "laterals": 4,
    "rhotics": 4,
    "approximants": 5,
    "glides": 5,
    "central_vowels": 6,
    "front_vowels": 6,
    "back_vowels": 6,
    "diphthongs": 6,
    "vowels": 6,
    "consonants": 1,  # generic fallback for consonant group
    "silence": -1,
}


def pg16_sonority(pg16_group: str) -> int:
    """Return sonority level for a BFA pg16 phoneme group.

    Returns -1 for silence, 0-6 for consonants-to-vowels.
    """
    return _PG16_SONORITY.get(pg16_group, 1)


def _is_vowel(pg16_group: str) -> bool:
    """Check if a pg16 group represents a vowel/nucleus."""
    return pg16_group in (
        "central_vowels", "front_vowels", "back_vowels",
        "diphthongs", "vowels",
    )


def syllabify_ipa(
    phonemes: list[Phoneme],
    pg16_groups: list[str],
    word: str,
    word_index: int,
) -> list[Syllable]:
    """Syllabify IPA phonemes using sonority sequencing + Maximum Onset Principle.

    Args:
        phonemes: Phoneme objects with real BFA timestamps.
        pg16_groups: BFA pg16 group label for each phoneme (parallel list).
        word: The parent word text.
        word_index: Position in transcript.

    Returns:
        List of Syllable objects with real timestamps from BFA.
    """
    if not phonemes:
        return []

    if len(phonemes) != len(pg16_groups):
        raise ValueError(
            f"phonemes ({len(phonemes)}) and pg16_groups ({len(pg16_groups)}) "
            f"must have same length"
        )

    # Filter out silence phonemes
    filtered = [
        (ph, pg) for ph, pg in zip(phonemes, pg16_groups)
        if pg != "silence"
    ]
    if not filtered:
        return []

    phonemes_f, groups_f = zip(*filtered)
    phonemes_f = list(phonemes_f)
    groups_f = list(groups_f)

    # Find vowel nuclei indices
    nuclei_indices = [i for i, g in enumerate(groups_f) if _is_vowel(g)]

    # No vowels: treat entire sequence as one syllable
    if not nuclei_indices:
        return [Syllable(
            phonemes=phonemes_f,
            start=phonemes_f[0].start,
            end=phonemes_f[-1].end,
            word=word,
            word_index=word_index,
        )]

    # Find syllable boundaries using Maximum Onset Principle
    # Each nucleus gets surrounding consonants; maximize onset of following syllable
    boundaries = _find_boundaries(phonemes_f, groups_f, nuclei_indices)

    # Build syllables from boundaries
    syllables = []
    for start_idx, end_idx in boundaries:
        syl_phones = phonemes_f[start_idx:end_idx]
        if syl_phones:
            syllables.append(Syllable(
                phonemes=syl_phones,
                start=syl_phones[0].start,
                end=syl_phones[-1].end,
                word=word,
                word_index=word_index,
            ))

    return syllables


def _find_boundaries(
    phonemes: list[Phoneme],
    groups: list[str],
    nuclei_indices: list[int],
) -> list[tuple[int, int]]:
    """Find syllable boundary indices using Maximum Onset Principle.

    For each pair of adjacent nuclei, find the optimal split point
    in the consonant cluster between them that maximizes the onset
    of the following syllable while maintaining valid sonority rise.

    Returns list of (start_idx, end_idx) tuples (exclusive end).
    """
    n = len(phonemes)
    boundaries: list[tuple[int, int]] = []

    for syl_i in range(len(nuclei_indices)):
        nuc = nuclei_indices[syl_i]

        # Start of this syllable
        if syl_i == 0:
            syl_start = 0
        else:
            # Already set by previous iteration's split
            syl_start = boundaries[-1][1]

        # End of this syllable
        if syl_i == len(nuclei_indices) - 1:
            # Last syllable takes everything to the end
            syl_end = n
        else:
            # Find split point in consonant cluster between this and next nucleus
            next_nuc = nuclei_indices[syl_i + 1]
            syl_end = _split_cluster(groups, nuc, next_nuc)

        boundaries.append((syl_start, syl_end))

    return boundaries


def _split_cluster(
    groups: list[str],
    nuc_a: int,
    nuc_b: int,
) -> int:
    """Find split point between two nuclei using Maximum Onset Principle.

    Consonants between nuc_a and nuc_b: maximize onset (give as many
    as possible to the following syllable) while ensuring sonority
    rises toward the nucleus.

    Returns the index where the next syllable should start.
    """
    # Consonant cluster is groups[nuc_a+1 : nuc_b]
    cluster_start = nuc_a + 1
    cluster_end = nuc_b

    if cluster_start >= cluster_end:
        # No consonants between nuclei — split at nuc_b
        return nuc_b

    # Maximum Onset Principle: start with all consonants as onset of next syllable,
    # then move consonants to coda if they violate sonority sequencing.
    # Valid onset: sonority should rise toward the nucleus.
    cluster_len = cluster_end - cluster_start

    # Try giving all consonants to onset (maximum onset)
    # Then check if sonority rises — if not, peel off from the left
    for split in range(cluster_start, cluster_end + 1):
        # split = start of next syllable's onset
        onset = groups[split:cluster_end]
        if not onset:
            # All consonants go to coda
            return cluster_end

        if _valid_onset(onset):
            return split

    # Fallback: split in the middle
    return cluster_start + cluster_len // 2


def _valid_onset(onset_groups: list[str]) -> bool:
    """Check if a consonant sequence forms a valid onset (sonority rises).

    A valid onset has non-decreasing sonority leading into the nucleus.
    Single consonants are always valid. Empty onsets are valid.
    """
    if len(onset_groups) <= 1:
        return True

    sonorities = [pg16_sonority(g) for g in onset_groups]
    # Sonority should generally rise (or stay level) toward nucleus
    for i in range(len(sonorities) - 1):
        if sonorities[i] > sonorities[i + 1]:
            return False
    return True

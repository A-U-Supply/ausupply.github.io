"""Audio analysis utilities: WAV I/O, RMS energy, room tone, F0, breath detection, pink noise.

All functions operate on numpy arrays (float64, normalized to [-1, 1]).
WAV I/O uses scipy.io.wavfile for lightweight reading/writing without ffmpeg.
"""

from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile


# ---------------------------------------------------------------------------
# WAV I/O
# ---------------------------------------------------------------------------

def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    """Read a WAV file and return (samples, sample_rate).

    - Normalizes int16/int32 to float64 in [-1, 1]
    - Passes through float WAVs as float64
    - Takes the first channel if stereo

    Raises:
        FileNotFoundError: if the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    sr, data = wavfile.read(str(path))

    # Take first channel if stereo/multi-channel
    if data.ndim > 1:
        data = data[:, 0]

    # Normalize to float64 in [-1, 1]
    if np.issubdtype(data.dtype, np.integer):
        info = np.iinfo(data.dtype)
        samples = data.astype(np.float64) / max(abs(info.min), abs(info.max))
    else:
        samples = data.astype(np.float64)

    return samples, sr


def write_wav(path: str | Path, samples: np.ndarray, sr: int) -> None:
    """Write float64 samples to a 16-bit PCM WAV file.

    - Clips values to [-1, 1] before conversion
    - Creates parent directories if needed
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    clipped = np.clip(samples, -1.0, 1.0)
    int16 = (clipped * 32767).astype(np.int16)
    wavfile.write(str(path), sr, int16)


# ---------------------------------------------------------------------------
# RMS Energy
# ---------------------------------------------------------------------------

def compute_rms(samples: np.ndarray) -> float:
    """Compute RMS energy of the entire signal."""
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


def compute_rms_windowed(
    samples: np.ndarray,
    sr: int,
    window_ms: int = 100,
    hop_ms: int = 50,
) -> np.ndarray:
    """Compute RMS energy in sliding windows.

    Returns an array of RMS values, one per hop step.
    """
    window_samples = int(sr * window_ms / 1000)
    hop_samples = int(sr * hop_ms / 1000)

    if len(samples) < window_samples:
        return np.array([])

    n_frames = (len(samples) - window_samples) // hop_samples + 1
    rms = np.empty(n_frames)

    for i in range(n_frames):
        start = i * hop_samples
        frame = samples[start : start + window_samples]
        rms[i] = np.sqrt(np.mean(frame ** 2))

    return rms


# ---------------------------------------------------------------------------
# Room Tone Detection
# ---------------------------------------------------------------------------

def find_room_tone(
    samples: np.ndarray,
    sr: int,
    min_duration_ms: int = 500,
) -> tuple[float, float] | None:
    """Find the quietest continuous region at least min_duration_ms long.

    Uses windowed RMS to find frames below a quiet threshold, then finds the
    longest contiguous run of quiet frames.

    The threshold is set at 10% of the mean RMS, which separates quiet regions
    (room tone, silence) from speech/music. If the signal has no meaningful
    dynamic range (i.e., no frames fall below the threshold), returns None.

    Returns (start_s, end_s) or None if no suitable region is found.
    """
    min_samples = int(sr * min_duration_ms / 1000)
    if len(samples) < min_samples:
        return None

    # Use 25ms windows with 12ms hops for fine resolution
    window_ms = 25
    hop_ms = 12
    rms = compute_rms_windowed(samples, sr, window_ms=window_ms, hop_ms=hop_ms)

    if len(rms) == 0:
        return None

    mean_rms = rms.mean()

    # If mean is effectively zero, the whole signal is silent
    if mean_rms < 1e-10:
        return (0.0, len(samples) / sr)

    # Threshold: 10% of mean RMS separates quiet from active regions
    threshold = mean_rms * 0.1

    quiet_mask = rms < threshold

    # If no frames are quiet, there's no room tone to find
    if not quiet_mask.any():
        return None

    # Find longest run of True in quiet_mask
    best_start = 0
    best_length = 0
    current_start = 0
    current_length = 0

    for i, is_quiet in enumerate(quiet_mask):
        if is_quiet:
            if current_length == 0:
                current_start = i
            current_length += 1
            if current_length > best_length:
                best_length = current_length
                best_start = current_start
        else:
            current_length = 0

    # Convert frame indices to time
    hop_samples = int(sr * hop_ms / 1000)
    start_s = best_start * hop_samples / sr
    end_s = (best_start + best_length) * hop_samples / sr

    # Check if the region meets minimum duration
    if (end_s - start_s) < min_duration_ms / 1000:
        return None

    return (start_s, end_s)


# ---------------------------------------------------------------------------
# F0 Pitch Estimation
# ---------------------------------------------------------------------------

def estimate_f0(
    samples: np.ndarray,
    sr: int,
    f0_min: int = 50,
    f0_max: int = 400,
) -> float | None:
    """Estimate fundamental frequency using autocorrelation.

    Finds the first autocorrelation peak above a periodicity threshold,
    searching from the shortest lag (highest frequency) to avoid octave errors.

    Returns F0 in Hz, or None for silence, noise, or weak periodicity.
    """
    if len(samples) == 0:
        return None

    # Check for silence
    rms = compute_rms(samples)
    if rms < 1e-6:
        return None

    # Lag range corresponding to [f0_min, f0_max]
    # lag_min -> f0_max, lag_max -> f0_min
    lag_min = int(sr / f0_max)
    lag_max = int(sr / f0_min)

    # Clamp lag_max to signal length
    lag_max = min(lag_max, len(samples) - 1)
    if lag_min >= lag_max:
        return None

    # Compute normalized autocorrelation for the valid lag range
    x = samples - np.mean(samples)
    autocorr_0 = np.sum(x ** 2)
    if autocorr_0 < 1e-12:
        return None

    autocorr = np.empty(lag_max - lag_min + 1)
    for i, lag in enumerate(range(lag_min, lag_max + 1)):
        autocorr[i] = np.sum(x[:len(x) - lag] * x[lag:]) / autocorr_0

    # Find the first peak above threshold, scanning from shortest lag
    # (highest frequency) to avoid octave errors. A "peak" is a local
    # maximum: value >= both neighbors (or at boundary, >= the one neighbor).
    threshold = 0.3

    # Check left boundary first (lag_min = highest frequency in range)
    if len(autocorr) >= 2 and autocorr[0] >= threshold and autocorr[0] >= autocorr[1]:
        return float(sr / lag_min)

    # Scan interior points
    for i in range(1, len(autocorr) - 1):
        if (autocorr[i] >= threshold
                and autocorr[i] >= autocorr[i - 1]
                and autocorr[i] >= autocorr[i + 1]):
            best_lag = lag_min + i
            return float(sr / best_lag)

    return None


# ---------------------------------------------------------------------------
# Breath Detection
# ---------------------------------------------------------------------------

def find_breaths(
    samples: np.ndarray,
    sr: int,
    word_boundaries: list[tuple[float, float]],
    min_gap_ms: int = 200,
    max_gap_ms: int = 600,
) -> list[tuple[float, float]]:
    """Find breath-like sounds in inter-word gaps.

    A breath is an inter-word gap in [min_gap_ms, max_gap_ms] whose RMS
    is between 1% and 30% of the speech RMS level.

    Returns list of (start_s, end_s) tuples.
    """
    if len(word_boundaries) < 2:
        return []

    # Sort boundaries by start time
    sorted_bounds = sorted(word_boundaries, key=lambda x: x[0])

    # Compute speech RMS (from word regions)
    speech_samples = []
    for start, end in sorted_bounds:
        s = int(start * sr)
        e = int(end * sr)
        s = max(0, min(s, len(samples)))
        e = max(0, min(e, len(samples)))
        if e > s:
            speech_samples.append(samples[s:e])

    if not speech_samples:
        return []

    speech_rms = compute_rms(np.concatenate(speech_samples))
    if speech_rms < 1e-6:
        return []

    # Find inter-word gaps
    min_gap_s = min_gap_ms / 1000
    max_gap_s = max_gap_ms / 1000

    breaths = []
    for i in range(len(sorted_bounds) - 1):
        gap_start = sorted_bounds[i][1]
        gap_end = sorted_bounds[i + 1][0]
        gap_duration = gap_end - gap_start

        if gap_duration < min_gap_s or gap_duration > max_gap_s:
            continue

        # Extract gap samples
        s = int(gap_start * sr)
        e = int(gap_end * sr)
        s = max(0, min(s, len(samples)))
        e = max(0, min(e, len(samples)))
        if e <= s:
            continue

        gap_rms = compute_rms(samples[s:e])
        ratio = gap_rms / speech_rms

        # Breath heuristic: energy between 1% and 30% of speech level
        if 0.01 <= ratio <= 0.30:
            breaths.append((gap_start, gap_end))

    return breaths


# ---------------------------------------------------------------------------
# Pink Noise Generation
# ---------------------------------------------------------------------------

def generate_pink_noise(
    duration_s: float,
    sr: int,
    seed: int | None = None,
) -> np.ndarray:
    """Generate pink noise (1/f spectrum) via spectral shaping.

    White noise FFT -> multiply by 1/sqrt(f) -> IFFT -> normalize to [-1, 1].
    """
    n_samples = int(duration_s * sr)
    if n_samples == 0:
        return np.array([])

    rng = np.random.RandomState(seed)
    white = rng.randn(n_samples)

    # FFT
    fft = np.fft.rfft(white)

    # Build 1/sqrt(f) filter, avoiding division by zero at DC
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sr)
    freqs[0] = 1.0  # avoid div-by-zero; DC component gets multiplied by 1
    pink_filter = 1.0 / np.sqrt(freqs)

    # Apply filter
    fft *= pink_filter

    # IFFT back to time domain
    pink = np.fft.irfft(fft, n=n_samples)

    # Normalize to [-1, 1]
    peak = np.max(np.abs(pink))
    if peak > 0:
        pink /= peak

    return pink

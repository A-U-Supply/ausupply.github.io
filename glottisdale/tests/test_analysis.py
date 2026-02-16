"""Tests for audio analysis functions (WAV I/O, RMS, room tone, F0, breaths, pink noise)."""

from pathlib import Path

import numpy as np
import pytest
import scipy.io.wavfile as wavfile

from glottisdale.analysis import (
    compute_rms,
    compute_rms_windowed,
    estimate_f0,
    find_breaths,
    find_room_tone,
    generate_pink_noise,
    read_wav,
    write_wav,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sine(freq: float, duration: float, sr: int = 16000) -> np.ndarray:
    """Generate a sine wave at the given frequency."""
    t = np.arange(int(sr * duration)) / sr
    return np.sin(2 * np.pi * freq * t)


def _write_int16_wav(path: Path, samples: np.ndarray, sr: int = 16000) -> None:
    """Write a float64 array as int16 WAV (for testing read_wav)."""
    clipped = np.clip(samples, -1.0, 1.0)
    int16 = (clipped * 32767).astype(np.int16)
    wavfile.write(str(path), sr, int16)


def _write_int32_wav(path: Path, samples: np.ndarray, sr: int = 16000) -> None:
    """Write a float64 array as int32 WAV."""
    clipped = np.clip(samples, -1.0, 1.0)
    int32 = (clipped * 2147483647).astype(np.int32)
    wavfile.write(str(path), sr, int32)


def _write_float32_wav(path: Path, samples: np.ndarray, sr: int = 16000) -> None:
    """Write a float64 array as float32 WAV."""
    wavfile.write(str(path), sr, samples.astype(np.float32))


# ===========================================================================
# 1. read_wav
# ===========================================================================

class TestReadWav:
    def test_reads_fixture(self):
        """Read the existing test_tone.wav fixture."""
        samples, sr = read_wav(FIXTURES / "test_tone.wav")
        assert sr == 16000
        assert samples.dtype == np.float64
        assert len(samples) == 32000  # 2s at 16kHz
        assert -1.0 <= samples.min() and samples.max() <= 1.0

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_wav(Path("/nonexistent/file.wav"))

    def test_int16_normalization(self, tmp_path):
        """int16 samples are normalized to [-1, 1]."""
        original = _make_sine(440, 0.5)
        _write_int16_wav(tmp_path / "test.wav", original)
        samples, sr = read_wav(tmp_path / "test.wav")
        assert samples.dtype == np.float64
        assert -1.0 <= samples.min() and samples.max() <= 1.0
        # Should be close to original (within quantization error)
        np.testing.assert_allclose(samples, original, atol=1e-4)

    def test_int32_normalization(self, tmp_path):
        """int32 samples are normalized to [-1, 1]."""
        original = _make_sine(440, 0.5)
        _write_int32_wav(tmp_path / "test.wav", original)
        samples, sr = read_wav(tmp_path / "test.wav")
        assert samples.dtype == np.float64
        assert -1.0 <= samples.min() and samples.max() <= 1.0

    def test_float_input(self, tmp_path):
        """Float WAVs are passed through (already in [-1, 1] range)."""
        original = _make_sine(440, 0.5)
        _write_float32_wav(tmp_path / "test.wav", original)
        samples, sr = read_wav(tmp_path / "test.wav")
        assert samples.dtype == np.float64
        np.testing.assert_allclose(samples, original, atol=1e-6)

    def test_stereo_takes_first_channel(self, tmp_path):
        """Stereo input: only the first channel is returned."""
        left = _make_sine(440, 0.5)
        right = _make_sine(880, 0.5)
        stereo = np.column_stack([left, right])
        int16_stereo = (stereo * 32767).astype(np.int16)
        wavfile.write(str(tmp_path / "stereo.wav"), 16000, int16_stereo)

        samples, sr = read_wav(tmp_path / "stereo.wav")
        assert samples.ndim == 1
        assert len(samples) == len(left)
        # Should match the left channel
        np.testing.assert_allclose(samples, left, atol=1e-4)


# ===========================================================================
# 2. RMS Energy
# ===========================================================================

class TestComputeRms:
    def test_silence_is_zero(self):
        assert compute_rms(np.zeros(1000)) == 0.0

    def test_sine_wave(self):
        """RMS of a sine wave is 1/sqrt(2) ~ 0.7071."""
        sine = _make_sine(440, 1.0)
        rms = compute_rms(sine)
        assert abs(rms - 1 / np.sqrt(2)) < 0.01

    def test_dc_offset(self):
        """RMS of constant signal equals its absolute value."""
        dc = np.full(1000, 0.5)
        assert abs(compute_rms(dc) - 0.5) < 1e-6

    def test_empty_array(self):
        """Empty array should return 0."""
        assert compute_rms(np.array([])) == 0.0


class TestComputeRmsWindowed:
    def test_returns_array(self):
        samples = _make_sine(440, 1.0)
        result = compute_rms_windowed(samples, sr=16000)
        assert isinstance(result, np.ndarray)
        assert len(result) > 0

    def test_window_count(self):
        """Number of windows matches expected hop calculation."""
        sr = 16000
        duration = 1.0
        window_ms = 100
        hop_ms = 50
        samples = _make_sine(440, duration, sr)
        result = compute_rms_windowed(samples, sr, window_ms=window_ms, hop_ms=hop_ms)

        window_samples = int(sr * window_ms / 1000)
        hop_samples = int(sr * hop_ms / 1000)
        expected_frames = max(0, (len(samples) - window_samples) // hop_samples + 1)
        assert len(result) == expected_frames

    def test_sine_all_frames_similar(self):
        """Windowed RMS of a continuous sine should be roughly uniform."""
        samples = _make_sine(440, 1.0)
        result = compute_rms_windowed(samples, sr=16000)
        assert result.std() < 0.01  # Very little variation

    def test_loud_then_quiet(self):
        """Loud followed by quiet region should show a drop in windowed RMS."""
        sr = 16000
        loud = _make_sine(440, 0.5, sr) * 0.9
        quiet = np.zeros(int(sr * 0.5))
        samples = np.concatenate([loud, quiet])
        result = compute_rms_windowed(samples, sr)

        midpoint = len(result) // 2
        loud_rms = result[:midpoint].mean()
        quiet_rms = result[midpoint:].mean()
        assert loud_rms > quiet_rms * 5


# ===========================================================================
# 3. Room Tone Detection
# ===========================================================================

class TestFindRoomTone:
    def test_finds_quiet_region(self):
        """Detect the quiet region in a loud-quiet-loud signal."""
        sr = 16000
        loud = _make_sine(440, 1.0, sr) * 0.8
        quiet = np.random.RandomState(42).randn(int(sr * 1.0)) * 0.001  # very quiet noise
        signal = np.concatenate([loud, quiet, loud])

        result = find_room_tone(signal, sr, min_duration_ms=500)
        assert result is not None
        start, end = result
        # The quiet region is from 1.0 to 2.0 seconds
        assert 0.8 <= start <= 1.3
        assert 1.7 <= end <= 2.2
        assert (end - start) >= 0.5

    def test_all_silence(self):
        """All-silent signal: returns the whole thing (or a large chunk)."""
        sr = 16000
        silence = np.zeros(int(sr * 2.0))
        result = find_room_tone(silence, sr)
        # Should find something since the entire signal is quiet
        assert result is not None

    def test_too_short(self):
        """Audio shorter than min_duration_ms returns None."""
        sr = 16000
        short = np.zeros(int(sr * 0.1))  # 100ms
        result = find_room_tone(short, sr, min_duration_ms=500)
        assert result is None

    def test_no_quiet_region(self):
        """Continuous loud signal with no quiet region returns None."""
        sr = 16000
        loud = _make_sine(440, 2.0, sr) * 0.9
        result = find_room_tone(loud, sr, min_duration_ms=500)
        assert result is None


# ===========================================================================
# 4. F0 Pitch Estimation
# ===========================================================================

class TestEstimateF0:
    def test_300hz_sine(self):
        """Detect a mid-range pitch (300Hz)."""
        samples = _make_sine(300, 0.5)
        f0 = estimate_f0(samples, sr=16000)
        assert f0 is not None
        assert abs(f0 - 300) < 10  # within 10Hz

    def test_200hz_sine(self):
        """Detect a lower pitch."""
        samples = _make_sine(200, 0.5)
        f0 = estimate_f0(samples, sr=16000)
        assert f0 is not None
        assert abs(f0 - 200) < 10

    def test_100hz_sine(self):
        """Detect male speech range pitch."""
        samples = _make_sine(100, 0.5)
        f0 = estimate_f0(samples, sr=16000)
        assert f0 is not None
        assert abs(f0 - 100) < 10

    def test_silence_returns_none(self):
        """Silence has no pitch."""
        silence = np.zeros(16000)
        assert estimate_f0(silence, sr=16000) is None

    def test_noise_returns_none(self):
        """White noise has no clear pitch."""
        rng = np.random.RandomState(42)
        noise = rng.randn(16000) * 0.1
        assert estimate_f0(noise, sr=16000) is None

    def test_respects_max_range(self):
        """A pitch well above f0_max returns None or a subharmonic."""
        # 600Hz is well above f0_max=400; autocorrelation in range
        # should show only negative or weak values for a pure 600Hz sine
        samples = _make_sine(600, 0.5, sr=16000)
        f0 = estimate_f0(samples, sr=16000, f0_max=400)
        # 600Hz has period ~26.7 samples; the fundamental is outside range.
        # Any detection would be a subharmonic (300Hz). Accept that or None.
        if f0 is not None:
            # Should not report a frequency above f0_max
            assert f0 <= 400

    def test_narrow_range(self):
        """A pitch outside a narrow range is not detected in that range."""
        # 300Hz should not be detected in [100, 200] range
        samples = _make_sine(300, 0.5, sr=16000)
        f0 = estimate_f0(samples, sr=16000, f0_min=100, f0_max=200)
        # 300Hz's period ~53 samples; lag range for [100,200] is [80,160]
        # At lag=80 (200Hz), a 300Hz sine has moderate autocorrelation
        # but the first peak should be at the subharmonic of 300Hz (150Hz)
        if f0 is not None:
            assert 100 <= f0 <= 200


# ===========================================================================
# 5. Breath Detection
# ===========================================================================

class TestFindBreaths:
    def test_finds_breath_in_gap(self):
        """Detect a breath-like signal between two speech segments."""
        sr = 16000
        speech_level = 0.5
        # Simulate speech - quiet gap with faint noise - speech
        speech1 = _make_sine(200, 0.5, sr) * speech_level
        breath = np.random.RandomState(42).randn(int(sr * 0.3)) * 0.02  # faint noise
        speech2 = _make_sine(200, 0.5, sr) * speech_level

        signal = np.concatenate([speech1, breath, speech2])
        word_boundaries = [(0.0, 0.5), (0.8, 1.3)]

        breaths = find_breaths(signal, sr, word_boundaries)
        assert len(breaths) >= 1
        start, end = breaths[0]
        assert 0.4 <= start <= 0.6
        assert 0.7 <= end <= 0.9

    def test_no_gaps(self):
        """Continuous speech with no inter-word gaps yields no breaths."""
        sr = 16000
        speech = _make_sine(200, 1.0, sr)
        # Words are contiguous
        word_boundaries = [(0.0, 0.5), (0.5, 1.0)]
        breaths = find_breaths(speech, sr, word_boundaries)
        assert breaths == []

    def test_gap_too_short(self):
        """Gaps shorter than min_gap_ms are ignored."""
        sr = 16000
        speech = _make_sine(200, 1.0, sr) * 0.5
        # Gap is only 100ms (< 200ms default min)
        word_boundaries = [(0.0, 0.4), (0.5, 1.0)]
        breaths = find_breaths(speech, sr, word_boundaries, min_gap_ms=200)
        assert breaths == []

    def test_gap_too_long(self):
        """Gaps longer than max_gap_ms are ignored."""
        sr = 16000
        speech1 = _make_sine(200, 0.3, sr) * 0.5
        silence = np.zeros(int(sr * 1.0))  # 1 second gap
        speech2 = _make_sine(200, 0.3, sr) * 0.5
        signal = np.concatenate([speech1, silence, speech2])
        word_boundaries = [(0.0, 0.3), (1.3, 1.6)]
        breaths = find_breaths(signal, sr, word_boundaries, max_gap_ms=600)
        assert breaths == []

    def test_empty_boundaries(self):
        """No word boundaries means no breaths."""
        sr = 16000
        signal = _make_sine(200, 1.0, sr)
        assert find_breaths(signal, sr, []) == []

    def test_single_word(self):
        """Single word has no inter-word gaps."""
        sr = 16000
        signal = _make_sine(200, 1.0, sr)
        assert find_breaths(signal, sr, [(0.0, 1.0)]) == []


# ===========================================================================
# 6. Pink Noise Generation
# ===========================================================================

class TestGeneratePinkNoise:
    def test_shape_and_range(self):
        """Output has correct shape and is normalized to [-1, 1]."""
        noise = generate_pink_noise(1.0, sr=16000)
        assert len(noise) == 16000
        assert noise.max() <= 1.0
        assert noise.min() >= -1.0

    def test_reproducible_with_seed(self):
        """Same seed produces identical output."""
        a = generate_pink_noise(0.5, sr=16000, seed=42)
        b = generate_pink_noise(0.5, sr=16000, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_different_seeds_differ(self):
        """Different seeds produce different output."""
        a = generate_pink_noise(0.5, sr=16000, seed=42)
        b = generate_pink_noise(0.5, sr=16000, seed=99)
        assert not np.array_equal(a, b)

    def test_spectrum_is_pink(self):
        """Pink noise has more energy at low frequencies than high.

        Compare average power in low-frequency vs high-frequency bands.
        """
        sr = 16000
        noise = generate_pink_noise(2.0, sr=sr, seed=42)
        fft = np.fft.rfft(noise)
        power = np.abs(fft) ** 2
        n_bins = len(power)

        low_band = power[1:n_bins // 4].mean()   # low quarter
        high_band = power[3 * n_bins // 4:].mean()  # high quarter
        assert low_band > high_band * 2  # low freqs should dominate

    def test_zero_duration(self):
        """Zero-duration request returns empty array."""
        noise = generate_pink_noise(0.0, sr=16000)
        assert len(noise) == 0


# ===========================================================================
# 9. Write WAV
# ===========================================================================

class TestWriteWav:
    def test_roundtrip(self, tmp_path):
        """Write then read back should preserve the signal."""
        original = _make_sine(440, 0.5)
        path = tmp_path / "out.wav"
        write_wav(path, original, sr=16000)

        # Read back with scipy directly to verify format
        sr, data = wavfile.read(str(path))
        assert sr == 16000
        assert data.dtype == np.int16  # output is 16-bit PCM

        # Read back with our own read_wav
        samples, sr2 = read_wav(path)
        assert sr2 == 16000
        np.testing.assert_allclose(samples, original, atol=1e-4)

    def test_clips_values(self, tmp_path):
        """Values outside [-1, 1] are clipped before writing."""
        signal = np.array([-2.0, -1.5, 0.0, 1.5, 2.0])
        path = tmp_path / "clipped.wav"
        write_wav(path, signal, sr=16000)

        samples, _ = read_wav(path)
        assert samples.min() >= -1.0
        assert samples.max() <= 1.0

    def test_path_as_string(self, tmp_path):
        """Accepts both Path and string."""
        signal = _make_sine(440, 0.1)
        path = str(tmp_path / "string_path.wav")
        write_wav(path, signal, sr=16000)
        samples, sr = read_wav(Path(path))
        assert len(samples) == len(signal)

    def test_creates_parent_dirs(self, tmp_path):
        """Creates parent directories if they don't exist."""
        signal = _make_sine(440, 0.1)
        path = tmp_path / "subdir" / "nested" / "out.wav"
        write_wav(path, signal, sr=16000)
        assert path.exists()

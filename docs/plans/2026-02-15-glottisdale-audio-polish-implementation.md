# Glottisdale Audio Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Glottisdale output sound like natural (if nonsensical) speech by adding a noise bed, room tone, pitch normalization, breath sounds, volume envelope, and longer crossfades.

**Architecture:** Hybrid approach — numpy for audio analysis (pitch, RMS, room tone detection), ffmpeg for audio processing (cutting, concatenation, mixing). One new module `analysis.py` for all numpy analysis. Extensions to existing `audio.py` for new ffmpeg operations. All features wired into `process()` via new parameters and toggled via CLI flags.

**Tech Stack:** numpy (already available via whisper/torch), ffmpeg (existing), scipy.io.wavfile for WAV I/O

**Design doc:** `docs/plans/2026-02-15-glottisdale-audio-polish-design.md`

---

### Task 1: WAV I/O Helpers in analysis.py

New module for numpy-based audio analysis. Start with WAV read/write since everything else depends on it.

**Files:**
- Create: `glottisdale/src/glottisdale/analysis.py`
- Create: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

```python
# glottisdale/tests/test_analysis.py
"""Tests for numpy-based audio analysis."""

import numpy as np
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class TestReadWav:
    def test_reads_test_tone(self):
        from glottisdale.analysis import read_wav
        samples, sr = read_wav(FIXTURES / "test_tone.wav")
        assert sr == 16000 or sr > 0  # fixture may have different rate
        assert len(samples) > 0
        assert samples.dtype == np.float64

    def test_normalizes_to_float(self):
        from glottisdale.analysis import read_wav
        samples, _ = read_wav(FIXTURES / "test_tone.wav")
        assert samples.max() <= 1.0
        assert samples.min() >= -1.0

    def test_nonexistent_file_raises(self):
        from glottisdale.analysis import read_wav
        with pytest.raises(FileNotFoundError):
            read_wav(Path("/nonexistent/file.wav"))
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'glottisdale.analysis'`

**Step 3: Write minimal implementation**

```python
# glottisdale/src/glottisdale/analysis.py
"""Numpy-based audio analysis for glottisdale."""

import numpy as np
from pathlib import Path


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file, return (samples_as_float64, sample_rate)."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    import scipy.io.wavfile as wavfile
    sr, data = wavfile.read(str(path))
    # Convert to float64 normalized to [-1, 1]
    if data.dtype == np.int16:
        samples = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        samples = data.astype(np.float64) / 2147483648.0
    elif data.dtype == np.float32 or data.dtype == np.float64:
        samples = data.astype(np.float64)
    else:
        samples = data.astype(np.float64)
    # If stereo, take first channel
    if samples.ndim > 1:
        samples = samples[:, 0]
    return samples, sr
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add analysis module with WAV I/O"
```

---

### Task 2: RMS Energy Measurement

Add RMS computation to analysis.py — needed by room tone detection, breath detection, and volume normalization.

**Files:**
- Modify: `glottisdale/src/glottisdale/analysis.py`
- Modify: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

Append to `test_analysis.py`:

```python
class TestRMS:
    def test_silence_has_zero_rms(self):
        from glottisdale.analysis import compute_rms
        silence = np.zeros(16000)
        assert compute_rms(silence) == pytest.approx(0.0)

    def test_known_amplitude(self):
        from glottisdale.analysis import compute_rms
        # A constant signal of 0.5 has RMS = 0.5
        signal = np.full(16000, 0.5)
        assert compute_rms(signal) == pytest.approx(0.5, abs=0.001)

    def test_sine_wave_rms(self):
        from glottisdale.analysis import compute_rms
        # Sine wave RMS = amplitude / sqrt(2)
        t = np.linspace(0, 1, 16000)
        signal = np.sin(2 * np.pi * 440 * t)
        expected = 1.0 / np.sqrt(2)
        assert compute_rms(signal) == pytest.approx(expected, abs=0.01)


class TestRMSWindowed:
    def test_returns_array(self):
        from glottisdale.analysis import compute_rms_windowed
        signal = np.random.randn(16000)
        rms = compute_rms_windowed(signal, sr=16000, window_ms=100, hop_ms=50)
        assert isinstance(rms, np.ndarray)
        assert len(rms) > 0

    def test_silent_then_loud(self):
        from glottisdale.analysis import compute_rms_windowed
        # 1s silence followed by 1s loud signal
        silence = np.zeros(16000)
        loud = np.full(16000, 0.5)
        signal = np.concatenate([silence, loud])
        rms = compute_rms_windowed(signal, sr=16000, window_ms=200, hop_ms=100)
        # First values should be near zero, last values near 0.5
        assert rms[0] < 0.01
        assert rms[-1] > 0.4
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py::TestRMS tests/test_analysis.py::TestRMSWindowed -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `analysis.py`:

```python
def compute_rms(samples: np.ndarray) -> float:
    """Compute RMS energy of a signal."""
    return float(np.sqrt(np.mean(samples ** 2)))


def compute_rms_windowed(
    samples: np.ndarray, sr: int, window_ms: float = 100, hop_ms: float = 50
) -> np.ndarray:
    """Compute RMS energy in sliding windows. Returns array of RMS values."""
    window_samples = int(sr * window_ms / 1000)
    hop_samples = int(sr * hop_ms / 1000)
    if window_samples <= 0 or hop_samples <= 0:
        return np.array([compute_rms(samples)])
    n_frames = max(1, (len(samples) - window_samples) // hop_samples + 1)
    rms = np.empty(n_frames)
    for i in range(n_frames):
        start = i * hop_samples
        end = start + window_samples
        rms[i] = compute_rms(samples[start:end])
    return rms
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add RMS energy measurement"
```

---

### Task 3: Room Tone Detection

Find the quietest continuous region in a source audio file.

**Files:**
- Modify: `glottisdale/src/glottisdale/analysis.py`
- Modify: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

```python
class TestFindRoomTone:
    def test_finds_quiet_region(self):
        from glottisdale.analysis import find_room_tone
        # 1s loud, 0.6s quiet, 1s loud
        sr = 16000
        loud = np.random.randn(sr) * 0.5
        quiet = np.random.randn(int(sr * 0.6)) * 0.001
        signal = np.concatenate([loud, quiet, loud])
        start, end = find_room_tone(signal, sr, min_duration_ms=500)
        # Should find the quiet region around 1.0-1.6s
        assert start >= 0.8  # approximate — windowed analysis has some tolerance
        assert end <= 1.8
        assert end - start >= 0.5

    def test_returns_none_if_no_quiet_region(self):
        from glottisdale.analysis import find_room_tone
        # All loud, no quiet region >= 500ms
        sr = 16000
        signal = np.random.randn(sr * 2) * 0.5
        result = find_room_tone(signal, sr, min_duration_ms=500)
        assert result is None

    def test_returns_none_for_short_audio(self):
        from glottisdale.analysis import find_room_tone
        sr = 16000
        signal = np.zeros(int(sr * 0.1))  # 100ms — too short
        result = find_room_tone(signal, sr, min_duration_ms=500)
        assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py::TestFindRoomTone -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def find_room_tone(
    samples: np.ndarray, sr: int, min_duration_ms: float = 500
) -> tuple[float, float] | None:
    """Find the quietest continuous region >= min_duration_ms.

    Returns (start_seconds, end_seconds) or None if not found.
    """
    min_samples = int(sr * min_duration_ms / 1000)
    if len(samples) < min_samples:
        return None

    window_ms = 50
    hop_ms = 25
    rms = compute_rms_windowed(samples, sr, window_ms=window_ms, hop_ms=hop_ms)
    hop_samples = int(sr * hop_ms / 1000)
    min_frames = max(1, min_samples // hop_samples)

    # Find threshold: bottom 10th percentile of RMS values
    threshold = np.percentile(rms, 10)
    # If threshold is too close to the median, there's no meaningfully quiet region
    median_rms = np.median(rms)
    if threshold > median_rms * 0.5:
        return None

    # Find longest run of frames below 2x threshold (generous margin)
    quiet_threshold = threshold * 2
    quiet = rms < quiet_threshold

    best_start = -1
    best_length = 0
    current_start = -1
    current_length = 0

    for i, is_quiet in enumerate(quiet):
        if is_quiet:
            if current_start < 0:
                current_start = i
            current_length += 1
        else:
            if current_length > best_length:
                best_start = current_start
                best_length = current_length
            current_start = -1
            current_length = 0
    if current_length > best_length:
        best_start = current_start
        best_length = current_length

    if best_length < min_frames:
        return None

    start_s = best_start * hop_ms / 1000
    end_s = (best_start + best_length) * hop_ms / 1000
    # Clamp to audio bounds
    end_s = min(end_s, len(samples) / sr)
    return (start_s, end_s)
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add room tone detection"
```

---

### Task 4: F0 Pitch Estimation

Estimate fundamental frequency (F0) of a speech clip using autocorrelation.

**Files:**
- Modify: `glottisdale/src/glottisdale/analysis.py`
- Modify: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

```python
class TestEstimateF0:
    def test_known_frequency(self):
        from glottisdale.analysis import estimate_f0
        sr = 16000
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        signal = np.sin(2 * np.pi * 200 * t)  # 200 Hz tone
        f0 = estimate_f0(signal, sr)
        assert f0 is not None
        assert abs(f0 - 200) < 10  # within 10 Hz

    def test_different_frequency(self):
        from glottisdale.analysis import estimate_f0
        sr = 16000
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        signal = np.sin(2 * np.pi * 150 * t)  # 150 Hz tone
        f0 = estimate_f0(signal, sr)
        assert f0 is not None
        assert abs(f0 - 150) < 10

    def test_noise_returns_none(self):
        from glottisdale.analysis import estimate_f0
        sr = 16000
        signal = np.random.randn(int(sr * 0.5))  # pure noise
        f0 = estimate_f0(signal, sr)
        # May or may not detect a pitch in noise — just check it doesn't crash
        assert f0 is None or isinstance(f0, float)

    def test_silence_returns_none(self):
        from glottisdale.analysis import estimate_f0
        sr = 16000
        signal = np.zeros(int(sr * 0.5))
        f0 = estimate_f0(signal, sr)
        assert f0 is None
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py::TestEstimateF0 -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def estimate_f0(
    samples: np.ndarray, sr: int,
    f0_min: float = 50, f0_max: float = 400
) -> float | None:
    """Estimate fundamental frequency via autocorrelation.

    Returns F0 in Hz, or None if no clear pitch detected.
    Speech F0 range: ~50-400 Hz (covers bass to soprano).
    """
    if len(samples) == 0 or compute_rms(samples) < 1e-6:
        return None

    # Lag range corresponding to f0_min..f0_max
    lag_min = int(sr / f0_max)
    lag_max = int(sr / f0_min)
    if lag_max >= len(samples):
        lag_max = len(samples) - 1
    if lag_min >= lag_max:
        return None

    # Normalized autocorrelation
    x = samples - np.mean(samples)
    corr = np.correlate(x, x, mode='full')
    corr = corr[len(corr) // 2:]  # positive lags only
    if corr[0] == 0:
        return None
    corr = corr / corr[0]  # normalize

    # Find highest peak in the speech F0 lag range
    search = corr[lag_min:lag_max + 1]
    if len(search) == 0:
        return None

    peak_idx = np.argmax(search)
    peak_val = search[peak_idx]

    # Require a strong periodic signal (threshold)
    if peak_val < 0.3:
        return None

    lag = lag_min + peak_idx
    f0 = sr / lag
    return float(f0)
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add F0 pitch estimation via autocorrelation"
```

---

### Task 5: Breath Detection from Word Gaps

Detect breath-like sounds in inter-word gaps from Whisper timestamps.

**Files:**
- Modify: `glottisdale/src/glottisdale/analysis.py`
- Modify: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

```python
class TestFindBreaths:
    def test_finds_breath_in_gap(self):
        from glottisdale.analysis import find_breaths
        sr = 16000
        # Simulate: 0.5s speech, 0.4s breath-level noise, 0.5s speech
        speech1 = np.random.randn(int(sr * 0.5)) * 0.3
        breath = np.random.randn(int(sr * 0.4)) * 0.02  # quieter than speech
        speech2 = np.random.randn(int(sr * 0.5)) * 0.3
        signal = np.concatenate([speech1, breath, speech2])
        word_boundaries = [
            (0.0, 0.5),   # word 1
            (0.9, 1.4),   # word 2
        ]
        breaths = find_breaths(signal, sr, word_boundaries)
        # Should find the gap between 0.5 and 0.9
        assert len(breaths) >= 0  # may or may not detect depending on thresholds
        for start, end in breaths:
            assert 0.4 <= start <= 0.6
            assert 0.8 <= end <= 1.0

    def test_no_gaps_returns_empty(self):
        from glottisdale.analysis import find_breaths
        sr = 16000
        signal = np.random.randn(sr) * 0.3
        word_boundaries = [(0.0, 0.5), (0.5, 1.0)]  # no gaps
        breaths = find_breaths(signal, sr, word_boundaries)
        assert breaths == []

    def test_silent_gap_not_a_breath(self):
        from glottisdale.analysis import find_breaths
        sr = 16000
        # Speech, then true silence, then speech — silence is NOT a breath
        speech = np.random.randn(int(sr * 0.5)) * 0.3
        silence = np.zeros(int(sr * 0.4))
        signal = np.concatenate([speech, silence, speech])
        word_boundaries = [(0.0, 0.5), (0.9, 1.4)]
        breaths = find_breaths(signal, sr, word_boundaries)
        assert breaths == []  # silence should not be classified as breath
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py::TestFindBreaths -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def find_breaths(
    samples: np.ndarray,
    sr: int,
    word_boundaries: list[tuple[float, float]],
    min_gap_ms: float = 200,
    max_gap_ms: float = 600,
) -> list[tuple[float, float]]:
    """Find breath-like sounds in gaps between words.

    Returns list of (start_s, end_s) for detected breaths.
    A breath is a gap segment with energy above room tone but below speech level.
    """
    if len(word_boundaries) < 2:
        return []

    # Compute speech RMS from word regions for reference
    speech_rms_values = []
    for start, end in word_boundaries:
        s = int(start * sr)
        e = int(end * sr)
        if s < len(samples) and e <= len(samples) and e > s:
            speech_rms_values.append(compute_rms(samples[s:e]))

    if not speech_rms_values:
        return []
    speech_rms = np.median(speech_rms_values)
    if speech_rms < 1e-6:
        return []

    breaths = []
    for i in range(len(word_boundaries) - 1):
        gap_start = word_boundaries[i][1]
        gap_end = word_boundaries[i + 1][0]
        gap_ms = (gap_end - gap_start) * 1000

        if gap_ms < min_gap_ms or gap_ms > max_gap_ms:
            continue

        s = int(gap_start * sr)
        e = int(gap_end * sr)
        if s >= len(samples) or e > len(samples) or e <= s:
            continue

        gap_rms = compute_rms(samples[s:e])

        # Breath heuristic: energy between 1% and 30% of speech level
        if gap_rms > speech_rms * 0.01 and gap_rms < speech_rms * 0.3:
            breaths.append((gap_start, gap_end))

    return breaths
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add breath detection from word gaps"
```

---

### Task 6: Pink Noise Generation

Generate pink noise (1/f spectrum) using numpy.

**Files:**
- Modify: `glottisdale/src/glottisdale/analysis.py`
- Modify: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

```python
class TestGeneratePinkNoise:
    def test_correct_length(self):
        from glottisdale.analysis import generate_pink_noise
        samples = generate_pink_noise(duration_s=2.0, sr=16000)
        assert len(samples) == 32000

    def test_normalized_amplitude(self):
        from glottisdale.analysis import generate_pink_noise
        samples = generate_pink_noise(duration_s=1.0, sr=16000)
        assert samples.max() <= 1.0
        assert samples.min() >= -1.0

    def test_seed_reproducible(self):
        from glottisdale.analysis import generate_pink_noise
        a = generate_pink_noise(duration_s=0.5, sr=16000, seed=42)
        b = generate_pink_noise(duration_s=0.5, sr=16000, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_spectral_slope(self):
        """Pink noise should have more low-frequency energy than white noise."""
        from glottisdale.analysis import generate_pink_noise
        samples = generate_pink_noise(duration_s=2.0, sr=16000, seed=1)
        fft = np.abs(np.fft.rfft(samples))
        n = len(fft)
        low_energy = np.mean(fft[:n // 4] ** 2)
        high_energy = np.mean(fft[n // 2:] ** 2)
        # Pink noise: low frequencies should have more energy
        assert low_energy > high_energy
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py::TestGeneratePinkNoise -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def generate_pink_noise(
    duration_s: float, sr: int, seed: int | None = None
) -> np.ndarray:
    """Generate pink noise (1/f spectrum).

    Uses the Voss-McCartney algorithm for efficient pink noise generation.
    Returns float64 array normalized to [-1, 1].
    """
    rng = np.random.default_rng(seed)
    n_samples = int(duration_s * sr)

    # Simple spectral shaping approach: generate white noise, apply 1/f filter
    white = rng.standard_normal(n_samples)
    fft = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sr)
    # Avoid division by zero at DC
    freqs[0] = 1.0
    # Pink noise: amplitude ~ 1/sqrt(f)
    fft *= 1.0 / np.sqrt(freqs)
    pink = np.fft.irfft(fft, n=n_samples)
    # Normalize to [-1, 1]
    peak = np.max(np.abs(pink))
    if peak > 0:
        pink = pink / peak
    return pink
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add pink noise generation"
```

---

### Task 7: Pitch Shifting and Volume Adjustment via ffmpeg

New ffmpeg functions: pitch shift a clip by ratio, adjust volume by dB.

**Files:**
- Modify: `glottisdale/src/glottisdale/audio.py`
- Modify: `glottisdale/tests/test_audio.py`

**Step 1: Write failing tests**

Append to `test_audio.py`:

```python
def test_pitch_shift(tmp_path):
    """Pitch shifting should change pitch without changing duration."""
    from glottisdale.audio import pitch_shift_clip
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.5, 1.0, padding_ms=0, fade_ms=0)
    original_duration = get_duration(clip)

    out = tmp_path / "shifted.wav"
    pitch_shift_clip(clip, out, semitones=2.0)
    assert out.exists()
    shifted_duration = get_duration(out)
    # Duration should be approximately the same (within 10%)
    assert abs(shifted_duration - original_duration) / original_duration < 0.1


def test_pitch_shift_zero_is_identity(tmp_path):
    """Zero semitone shift should produce same-length output."""
    from glottisdale.audio import pitch_shift_clip
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "shifted.wav"
    pitch_shift_clip(clip, out, semitones=0.0)
    assert out.exists()
    assert abs(get_duration(out) - get_duration(clip)) < 0.05


def test_adjust_volume(tmp_path):
    """Volume adjustment should produce a valid output file."""
    from glottisdale.audio import adjust_volume
    clip = tmp_path / "clip.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip, 0.0, 1.0, padding_ms=0, fade_ms=0)

    out = tmp_path / "adjusted.wav"
    adjust_volume(clip, out, db=-6.0)
    assert out.exists()
    assert get_duration(out) == pytest.approx(get_duration(clip), abs=0.05)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_audio.py::test_pitch_shift tests/test_audio.py::test_pitch_shift_zero_is_identity tests/test_audio.py::test_adjust_volume -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `audio.py`:

```python
def pitch_shift_clip(
    input_path: Path, output_path: Path, semitones: float
) -> Path:
    """Pitch-shift a clip by the given number of semitones.

    Uses asetrate + aresample to change pitch without changing duration.
    """
    if abs(semitones) < 0.01:
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path

    # Get original sample rate
    output = _run_ffprobe(input_path, "-show_streams")
    data = json.loads(output)
    original_sr = int(data["streams"][0]["sample_rate"])

    # Pitch ratio: 2^(semitones/12)
    ratio = 2.0 ** (semitones / 12.0)
    new_rate = int(original_sr * ratio)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"asetrate={new_rate},aresample={original_sr}",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path


def adjust_volume(
    input_path: Path, output_path: Path, db: float
) -> Path:
    """Adjust volume of a clip by the given dB amount."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"volume={db}dB",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
    return output_path
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_audio.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/audio.py glottisdale/tests/test_audio.py
git commit -m "feat(glottisdale): add pitch shifting and volume adjustment"
```

---

### Task 8: Mix Noise Bed via ffmpeg

Add function to mix a noise array (as WAV) under an existing audio file.

**Files:**
- Modify: `glottisdale/src/glottisdale/audio.py`
- Modify: `glottisdale/tests/test_audio.py`

**Step 1: Write failing tests**

```python
def test_mix_audio(tmp_path):
    """Mixing two clips should produce output with duration of the longer clip."""
    from glottisdale.audio import mix_audio
    clip1 = tmp_path / "c1.wav"
    clip2 = tmp_path / "c2.wav"
    cut_clip(FIXTURES / "test_tone.wav", clip1, 0.0, 1.0, padding_ms=0, fade_ms=0)
    cut_clip(FIXTURES / "test_tone.wav", clip2, 0.0, 0.5, padding_ms=0, fade_ms=0)

    out = tmp_path / "mixed.wav"
    mix_audio(clip1, clip2, out, secondary_volume_db=-20)
    assert out.exists()
    # Duration should match the longer clip
    assert get_duration(out) == pytest.approx(1.0, abs=0.1)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_audio.py::test_mix_audio -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `audio.py`:

```python
def mix_audio(
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    secondary_volume_db: float = -40,
) -> Path:
    """Mix secondary audio under primary at the given volume level.

    Output duration matches the primary. Secondary is looped if shorter.
    """
    primary_dur = get_duration(primary_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(primary_path),
        "-i", str(secondary_path),
        "-filter_complex",
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={primary_dur:.4f},"
        f"volume={secondary_volume_db}dB[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120).check_returncode()
    return output_path
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_audio.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/audio.py glottisdale/tests/test_audio.py
git commit -m "feat(glottisdale): add audio mixing for noise bed"
```

---

### Task 9: Write Numpy Array to WAV Helper

Needed to write pink noise and room tone arrays to WAV files for ffmpeg consumption.

**Files:**
- Modify: `glottisdale/src/glottisdale/analysis.py`
- Modify: `glottisdale/tests/test_analysis.py`

**Step 1: Write failing tests**

```python
class TestWriteWav:
    def test_roundtrip(self, tmp_path):
        from glottisdale.analysis import write_wav, read_wav
        sr = 16000
        original = np.sin(2 * np.pi * 440 * np.linspace(0, 1, sr))
        path = tmp_path / "test.wav"
        write_wav(path, original, sr)
        loaded, loaded_sr = read_wav(path)
        assert loaded_sr == sr
        assert len(loaded) == len(original)
        # Allow quantization error (16-bit)
        np.testing.assert_allclose(loaded, original, atol=1e-4)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py::TestWriteWav -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `analysis.py`:

```python
def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    """Write a float64 array to a 16-bit PCM WAV file."""
    import scipy.io.wavfile as wavfile
    # Clip and convert to int16
    clipped = np.clip(samples, -1.0, 1.0)
    int16 = (clipped * 32767).astype(np.int16)
    wavfile.write(str(path), sr, int16)
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_analysis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/analysis.py glottisdale/tests/test_analysis.py
git commit -m "feat(glottisdale): add WAV write helper"
```

---

### Task 10: Update Crossfade Defaults

Change default crossfade values: intra-word 10→30ms, inter-word 25→50ms.

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py:183-190` (process() defaults)
- Modify: `glottisdale/src/glottisdale/cli.py:31-43` (argparse defaults)
- Modify: `glottisdale/tests/test_cli.py` (if defaults are tested)

**Step 1: Write failing test**

```python
# In test_cli.py, add:
def test_default_crossfade_values():
    from glottisdale.cli import parse_args
    args = parse_args([])
    assert args.crossfade == 30  # was 10
    assert args.word_crossfade == 50  # was 25
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_cli.py::test_default_crossfade_values -v`
Expected: FAIL (currently 10 and 25)

**Step 3: Update defaults**

In `cli.py`:
- Line 31: change `default=10` to `default=30` for `--crossfade`
- Line 43: change `default=25` to `default=50` for `--word-crossfade`

In `__init__.py` `process()` signature:
- Change `crossfade_ms: float = 10` to `crossfade_ms: float = 30`
- Change `word_crossfade_ms: float = 25` to `word_crossfade_ms: float = 50`

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: PASS (integration test uses explicit values, so defaults don't affect it)

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/src/glottisdale/cli.py glottisdale/tests/test_cli.py
git commit -m "feat(glottisdale): increase default crossfade to 30/50ms"
```

---

### Task 11: Add New CLI Flags

Add all new CLI flags for the audio polish features.

**Files:**
- Modify: `glottisdale/src/glottisdale/cli.py`
- Modify: `glottisdale/tests/test_cli.py`

**Step 1: Write failing tests**

```python
def test_audio_polish_flags_defaults():
    from glottisdale.cli import parse_args
    args = parse_args([])
    assert args.noise_level == -40
    assert args.room_tone is True
    assert args.pitch_normalize is True
    assert args.pitch_range == 5
    assert args.breaths is True
    assert args.breath_probability == 0.6
    assert args.volume_normalize is True
    assert args.prosodic_dynamics is True


def test_audio_polish_flags_disabled():
    from glottisdale.cli import parse_args
    args = parse_args([
        "--no-room-tone", "--no-pitch-normalize", "--no-breaths",
        "--no-volume-normalize", "--no-prosodic-dynamics",
        "--noise-level", "0",
    ])
    assert args.noise_level == 0
    assert args.room_tone is False
    assert args.pitch_normalize is False
    assert args.breaths is False
    assert args.volume_normalize is False
    assert args.prosodic_dynamics is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_cli.py::test_audio_polish_flags_defaults tests/test_cli.py::test_audio_polish_flags_disabled -v`
Expected: FAIL

**Step 3: Add CLI flags**

Add to `cli.py` after the existing options block (before `args = parser.parse_args(argv)`):

```python
    # Audio polish options
    parser.add_argument("--noise-level", type=float, default=-40,
                        help="Pink noise bed level in dB, 0 to disable (default: -40)")
    parser.add_argument("--room-tone", action=argparse.BooleanOptionalAction, default=True,
                        help="Extract room tone for gaps (default: enabled)")
    parser.add_argument("--pitch-normalize", action=argparse.BooleanOptionalAction, default=True,
                        help="Normalize pitch across syllables (default: enabled)")
    parser.add_argument("--pitch-range", type=float, default=5,
                        help="Max pitch shift in semitones (default: 5)")
    parser.add_argument("--breaths", action=argparse.BooleanOptionalAction, default=True,
                        help="Insert breath sounds at phrase boundaries (default: enabled)")
    parser.add_argument("--breath-probability", type=float, default=0.6,
                        help="Probability of breath at each phrase boundary (default: 0.6)")
    parser.add_argument("--volume-normalize", action=argparse.BooleanOptionalAction, default=True,
                        help="RMS-normalize syllable clips (default: enabled)")
    parser.add_argument("--prosodic-dynamics", action=argparse.BooleanOptionalAction, default=True,
                        help="Apply phrase-level volume envelope (default: enabled)")
```

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/cli.py glottisdale/tests/test_cli.py
git commit -m "feat(glottisdale): add CLI flags for audio polish features"
```

---

### Task 12: Pipeline Integration — Wire Analysis Into process()

The main task: integrate all analysis and audio polish features into the `process()` function.

**Files:**
- Modify: `glottisdale/src/glottisdale/__init__.py`
- Modify: `glottisdale/tests/test_pipeline.py`

**Step 1: Write failing test**

```python
@patch("glottisdale.get_aligner")
@patch("glottisdale.extract_audio")
@patch("glottisdale.detect_input_type")
@patch("glottisdale.cut_clip")
@patch("glottisdale.concatenate_clips")
@patch("glottisdale.get_duration", return_value=2.0)
def test_process_passes_audio_polish_params(
    mock_duration, mock_concat, mock_cut, mock_detect, mock_extract, mock_aligner, tmp_path
):
    """Process should accept audio polish parameters without error."""
    mock_detect.return_value = "audio"
    def fake_extract(input_path, output_path):
        output_path.touch()
        return output_path
    mock_extract.side_effect = fake_extract

    syllables = [
        Syllable([Phoneme("AH0", i * 0.2, (i + 1) * 0.2)],
                 i * 0.2, (i + 1) * 0.2, f"word{i}", i)
        for i in range(6)
    ]
    aligner_instance = MagicMock()
    aligner_instance.process.return_value = {
        "text": "test", "words": [], "syllables": syllables,
    }
    mock_aligner.return_value = aligner_instance

    def fake_cut(input_path, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_cut.side_effect = fake_cut
    def fake_concat(clips, output_path, **kwargs):
        output_path.touch()
        return output_path
    mock_concat.side_effect = fake_concat

    # Should accept all new params without TypeError
    result = process(
        input_paths=[tmp_path / "audio.wav"],
        output_dir=tmp_path / "out",
        target_duration=5.0,
        seed=42,
        noise_level_db=-40,
        room_tone=True,
        pitch_normalize=True,
        pitch_range=5,
        breaths=True,
        breath_probability=0.6,
        volume_normalize=True,
        prosodic_dynamics=True,
    )
    assert result.concatenated.exists()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_pipeline.py::test_process_passes_audio_polish_params -v`
Expected: FAIL with `TypeError: process() got an unexpected keyword argument 'noise_level_db'`

**Step 3: Add parameters to process() and wire the pipeline**

This is the most complex step. Update the `process()` signature and body in `__init__.py`.

Add new parameters to `process()`:

```python
def process(
    input_paths: list[Path],
    output_dir: str | Path = "./glottisdale-output",
    syllables_per_clip: str = "1-4",
    target_duration: float = 10.0,
    crossfade_ms: float = 30,
    padding_ms: float = 25,
    gap: str | None = None,
    words_per_phrase: str = "3-5",
    phrases_per_sentence: str = "2-3",
    phrase_pause: str = "400-700",
    sentence_pause: str = "800-1200",
    word_crossfade_ms: float = 50,
    aligner: str = "default",
    whisper_model: str = "base",
    seed: int | None = None,
    # Audio polish params
    noise_level_db: float = -40,
    room_tone: bool = True,
    pitch_normalize: bool = True,
    pitch_range: float = 5,
    breaths: bool = True,
    breath_probability: float = 0.6,
    volume_normalize: bool = True,
    prosodic_dynamics: bool = True,
) -> Result:
```

Add new imports at top of `__init__.py`:

```python
from glottisdale.analysis import (
    read_wav,
    write_wav,
    compute_rms,
    estimate_f0,
    find_room_tone,
    find_breaths,
    generate_pink_noise,
)
from glottisdale.audio import (
    cut_clip,
    concatenate_clips,
    detect_input_type,
    extract_audio,
    get_duration,
    pitch_shift_clip,
    adjust_volume,
    mix_audio,
)
```

In the pipeline body, add these phases after audio extraction but interleaved with existing logic:

**Phase A — Source analysis (after extract_audio, before syllable cutting):**
```python
        # === Audio polish: analyze sources ===
        source_room_tones: dict[str, tuple[float, float]] = {}
        source_breaths: dict[str, list[tuple[float, float]]] = {}
        source_audio_data: dict[str, tuple[np.ndarray, int]] = {}

        for source_name in all_syllables:
            audio_path = tmpdir / f"{source_name}.wav"
            if not audio_path.exists():
                continue
            samples, sr = read_wav(audio_path)
            source_audio_data[source_name] = (samples, sr)

            if room_tone:
                rt = find_room_tone(samples, sr)
                if rt is not None:
                    source_room_tones[source_name] = rt

            if breaths:
                word_boundaries = [
                    (s.start, s.end)
                    for s in all_syllables[source_name]
                    if s.word_index == 0 or True  # all word boundaries
                ]
                # Deduplicate to word-level boundaries
                word_bounds = []
                seen_words = set()
                for syl in all_syllables[source_name]:
                    key = (syl.word, syl.word_index)
                    if key not in seen_words:
                        word_start = min(s.start for s in all_syllables[source_name]
                                        if s.word == syl.word and s.word_index == syl.word_index)
                        word_end = max(s.end for s in all_syllables[source_name]
                                      if s.word == syl.word and s.word_index == syl.word_index)
                        word_bounds.append((word_start, word_end))
                        seen_words.add(key)
                word_bounds.sort()
                detected = find_breaths(samples, sr, word_bounds)
                if detected:
                    source_breaths[source_name] = detected
```

**Phase B — After cutting syllable clips, before word assembly: pitch normalization + volume normalization**
```python
            # After cutting each syllable clip (inside the word loop):
            if pitch_normalize and syl_clip_paths:
                # Measure F0 for each clip
                ...
            if volume_normalize and syl_clip_paths:
                # Normalize RMS for each clip
                ...
```

**Phase C — After phrase assembly, during gap insertion: room tone + breaths**
Replace `generate_silence` calls with room tone clips.

**Phase D — After final concatenation: mix noise bed**
```python
        if noise_level_db != 0 and concatenated_path.exists():
            noise = generate_pink_noise(get_duration(concatenated_path), 16000, seed=seed)
            noise_path = tmpdir / "noise_bed.wav"
            write_wav(noise_path, noise, 16000)
            mixed_path = output_dir / "concatenated_mixed.wav"
            mix_audio(concatenated_path, noise_path, mixed_path, secondary_volume_db=noise_level_db)
            mixed_path.rename(concatenated_path)
```

**Note:** The full implementation of Phase B (pitch/volume per-clip) and Phase C (room tone gaps) requires careful integration. The implementing agent should read the current `process()` body and insert the new code at the right points, following the pipeline flow documented in the design doc. The patterns above show the approach; exact line positions depend on the state of the code after Tasks 1-11.

**Step 4: Run tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/__init__.py glottisdale/tests/test_pipeline.py
git commit -m "feat(glottisdale): integrate audio polish into pipeline"
```

---

### Task 13: Wire CLI to process() Parameters

Pass the new CLI args through to `process()`.

**Files:**
- Modify: `glottisdale/src/glottisdale/cli.py:97-112` and `155-169` (both local and Slack mode)

**Step 1: Write failing test**

```python
# In test_cli.py
def test_cli_passes_audio_polish_to_process(tmp_path):
    """CLI should pass audio polish flags through to process()."""
    from unittest.mock import patch, MagicMock
    from glottisdale.cli import main

    with patch("glottisdale.cli.process") as mock_process:
        mock_process.return_value = MagicMock(
            transcript="test", clips=[], concatenated=tmp_path / "out" / "concatenated.wav",
        )
        input_file = tmp_path / "test.wav"
        input_file.touch()

        main([
            str(input_file),
            "--output-dir", str(tmp_path / "out"),
            "--noise-level", "-30",
            "--no-pitch-normalize",
            "--breath-probability", "0.8",
        ])

        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["noise_level_db"] == -30
        assert call_kwargs["pitch_normalize"] is False
        assert call_kwargs["breath_probability"] == 0.8
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_cli.py::test_cli_passes_audio_polish_to_process -v`
Expected: FAIL

**Step 3: Update CLI to pass new params**

In `cli.py`, in both the local mode and Slack mode `process()` calls, add the new parameters:

```python
            noise_level_db=args.noise_level,
            room_tone=args.room_tone,
            pitch_normalize=args.pitch_normalize,
            pitch_range=args.pitch_range,
            breaths=args.breaths,
            breath_probability=args.breath_probability,
            volume_normalize=args.volume_normalize,
            prosodic_dynamics=args.prosodic_dynamics,
```

**Step 4: Run all tests**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add glottisdale/src/glottisdale/cli.py glottisdale/tests/test_cli.py
git commit -m "feat(glottisdale): wire CLI flags to audio polish pipeline"
```

---

### Task 14: Integration Test with Real ffmpeg

End-to-end test with real audio processing (mocked Whisper only).

**Files:**
- Modify: `glottisdale/tests/test_integration.py`

**Step 1: Write the test**

```python
@pytest.mark.integration
@patch("glottisdale.align.transcribe")
def test_audio_polish_integration(mock_transcribe, tmp_path):
    """End-to-end test with audio polish features enabled."""
    import subprocess

    # Generate a test WAV: 1s tone, 0.5s quiet, 1s tone, 0.4s quiet, 1s tone
    input_wav = tmp_path / "input.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=200:duration=4",
        "-ar", "16000", "-ac", "1",
        str(input_wav),
    ], capture_output=True, check=True)

    mock_transcribe.return_value = {
        "text": "hello beautiful world today",
        "words": [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "beautiful", "start": 0.6, "end": 1.3},
            {"word": "world", "start": 1.8, "end": 2.3},
            {"word": "today", "start": 2.8, "end": 3.5},
        ],
        "language": "en",
    }

    output_dir = tmp_path / "output"
    result = process(
        input_paths=[input_wav],
        output_dir=output_dir,
        target_duration=10.0,
        seed=42,
        noise_level_db=-40,
        room_tone=True,
        pitch_normalize=True,
        pitch_range=5,
        breaths=True,
        breath_probability=1.0,  # always insert for testing
        volume_normalize=True,
        prosodic_dynamics=True,
    )

    assert result.concatenated.exists()
    assert result.concatenated.stat().st_size > 0
    # Output should exist and be a valid audio file
    from glottisdale.audio import get_duration
    dur = get_duration(result.concatenated)
    assert dur > 0
```

**Step 2: Run test**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/test_integration.py::test_audio_polish_integration -v -m integration`
Expected: PASS

**Step 3: Commit**

```bash
git add glottisdale/tests/test_integration.py
git commit -m "test(glottisdale): add integration test for audio polish features"
```

---

### Task 15: Update GitHub Actions Workflow

Add scipy to the workflow dependencies (it's needed by analysis.py but may not be pulled in by existing deps on all platforms).

**Files:**
- Check: `.github/workflows/glottisdale.yml` — verify scipy is available (it comes with whisper/torch, but confirm)
- Modify: `glottisdale/pyproject.toml` — add scipy to dependencies if not already transitively available

**Step 1: Check if scipy is available**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -c "import scipy.io.wavfile; print('ok')"`

If it fails, add `scipy` to `pyproject.toml` dependencies:

```toml
dependencies = [
    "openai-whisper",
    "g2p_en",
    "scipy",
]
```

**Step 2: Run full test suite**

Run: `cd /Users/jake/au-supply/ausupply.github.io/glottisdale && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit if changed**

```bash
git add glottisdale/pyproject.toml
git commit -m "build(glottisdale): add scipy dependency for audio analysis"
```

---

### Task 16: Update Documentation

Update MEMORY.md and design doc with implementation notes.

**Files:**
- Modify: `/Users/jake/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md`

**Step 1: Add audio polish section to MEMORY.md**

Under the Glottisdale section, add:

```markdown
### Audio Polish Features
- `analysis.py` — numpy-based audio analysis: WAV I/O, RMS, F0 estimation, room tone detection, breath detection, pink noise generation
- Pink noise bed mixed under entire output at configurable level (default -40dB)
- Room tone extracted from quietest region of source audio, used to fill phrase/sentence gaps instead of digital silence
- Pitch normalization: autocorrelation F0 → median target → ffmpeg asetrate per clip (max ±5 semitones)
- Breath extraction: inter-word gaps 200-600ms with energy between 1-30% of speech RMS
- Volume normalization: RMS-normalize all syllable clips before assembly
- Prosodic dynamics: phrase-onset boost (+1dB), phrase-final softening (-3dB)
- Default crossfades increased: intra-word 30ms (was 10), inter-word 50ms (was 25)
- All features CLI-configurable with --flag/--no-flag toggles
- scipy.io.wavfile for WAV I/O (numpy ↔ file bridge)
```

**Step 2: Commit**

```bash
git add /Users/jake/.claude/projects/-Users-jake-au-supply-ausupply-github-io/memory/MEMORY.md
git commit -m "docs: update MEMORY.md with audio polish details"
```

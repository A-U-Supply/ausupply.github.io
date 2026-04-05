# Sparagmos — Design Spec

**Repo:** A-U-Supply/sparagmos (GitHub) / `~/au-supply/sparagmos` (local)
**Language:** Python (uv for project management, pytest for testing)
**Purpose:** Daily automated image destruction bot. Scrapes a random image from #image-gen on Slack, applies a randomly selected recipe of chained glitch/decay/neural effects, posts the result with full provenance to #img-junkyard — all in a single Slack message.

**Name origin:** σπαραγμός (sparagmos) — the ritual dismemberment in Dionysian mystery rites. The ecstatic tearing apart of a body as a sacred act. Destruction is the worship.

## Architecture

### Repository Structure

```
sparagmos/                      # ~/au-supply/sparagmos
├── sparagmos/                  # Python package
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point (argparse)
│   ├── config.py               # Recipe loading, YAML schema validation
│   ├── pipeline.py             # Effect chaining engine
│   ├── slack_source.py         # Scrape random image from #image-gen
│   ├── slack_post.py           # Post result to #img-junkyard (single msg)
│   ├── vision.py               # Llama Vision analysis via HF Inference API
│   ├── state.py                # JSON state: processed images, history
│   │
│   ├── effects/                # One module per effect type
│   │   ├── __init__.py         # Effect registry, base class, SubprocessEffect
│   │   ├── byte_corrupt.py     # Raw byte manipulation, hex corruption
│   │   ├── cellular.py         # Game of Life / Rule 110 on pixel data
│   │   ├── channel_shift.py    # RGB channel offset/swap/separation
│   │   ├── crt_vhs.py          # Scan lines, tracking errors, phosphor glow
│   │   ├── datamosh.py         # I-frame removal, motion vector swap
│   │   ├── deepdream.py        # Google DeepDream via PyTorch
│   │   ├── dither.py           # Floyd-Steinberg, Bayer, retro palettes
│   │   ├── format_roundtrip.py # Lossy JPEG chain, potrace round-trip
│   │   ├── fractal_blend.py    # Mandelbrot at image-derived coordinates
│   │   ├── imagemagick.py      # Wrapper: -implode, -swirl, -fx, -morphology
│   │   ├── inpaint.py          # Selective mask + regenerate (small diffusion)
│   │   ├── jpeg_destroy.py     # Multi-generation JPEG compression
│   │   ├── netpbm.py           # Wrapper: pgmcrater, ppmforge, ppmspread
│   │   ├── neural_doodle.py    # Semantic style painting
│   │   ├── pca_decompose.py    # Eigenface/PCA reconstruction
│   │   ├── pix2pix.py          # Image-to-image translation (CycleGAN)
│   │   ├── pixel_sort.py       # Sort by brightness/hue/saturation
│   │   ├── primitive.py        # Geometric shape reconstruction
│   │   ├── seam_carve.py       # Content-aware resize, intentionally broken
│   │   ├── sonify.py           # Image → raw audio → DSP → image
│   │   ├── spectral.py         # Spectrogram/Photosounder treatment
│   │   └── style_transfer.py   # Gatys neural style transfer
│   │
│   └── vendor/                 # Vendored dependencies (see Vendoring section)
│       ├── README.md           # Provenance: source, version, modifications
│       └── ...
│
├── recipes/                    # YAML recipe files
│   ├── vhs-meltdown.yaml
│   ├── deep-fossil.yaml
│   ├── cga-nightmare.yaml
│   ├── dionysian-rite.yaml
│   ├── analog-burial.yaml
│   ├── byte-liturgy.yaml
│   ├── thermal-ghost.yaml
│   ├── turtle-oracle.yaml
│   ├── eigenface-requiem.yaml
│   ├── spectral-autopsy.yaml
│   ├── ocr-feedback-loop.yaml
│   ├── cellular-decay.yaml
│   └── ... (~12-15 starter recipes)
│
├── tests/
│   ├── conftest.py             # Shared fixtures (test images, tmp dirs)
│   ├── fixtures/               # Small test images (various formats/sizes)
│   ├── test_effects/           # Unit tests per effect module
│   │   ├── test_pixel_sort.py
│   │   ├── test_deepdream.py
│   │   ├── test_byte_corrupt.py
│   │   └── ... (one per effect)
│   ├── test_config.py          # Recipe schema validation
│   ├── test_pipeline.py        # Effect chaining integration
│   ├── test_recipes.py         # Load + validate every recipe in recipes/
│   └── test_slack.py           # Slack I/O (mocked)
│
├── docs/
│   ├── recipes.md              # How to create recipes, full param reference
│   └── effects.md              # Per-effect documentation and examples
│
├── state.json                  # Processed image history (committed)
├── pyproject.toml              # uv project config
├── requirements.txt            # For GitHub Actions pip install
├── README.md                   # Overview, effects table, quickstart
└── .github/
    └── workflows/
        └── sparagmos.yml       # Daily cron + manual trigger
```

### Data Flow

```
#image-gen (Slack)
    │
    │ 1. Pick random image (not previously processed)
    ▼
slack_source.py
    │  Download image, record in state.json
    │
    │ 2. Optionally analyze with Llama Vision
    ▼
vision.py (HF Inference API)
    │  "Face top-left, landscape behind, text overlay"
    │  Provides targeting hints for vision-aware recipes
    │
    │ 3. Pick random recipe from recipes/
    ▼
config.py
    │  Load YAML, validate against effect schemas,
    │  resolve param ranges (roll random values)
    │
    │ 4. Execute effect chain
    ▼
pipeline.py
    │  effect₁ → effect₂ → effect₃ → ... → result
    │  Each effect: PIL.Image in → PIL.Image out
    │
    │ 5. Post to Slack (single message)
    ▼
#img-junkyard (Slack)
    Image + recipe name + effects chain + source attribution
    All in one message via files_upload_v2 initial_comment
```

## Effect Module Interface

Every effect implements the same contract:

```python
class Effect(ABC):
    name: str                    # e.g. "pixel_sort"
    description: str             # Human-readable, used in Slack posts
    requires: list[str]          # System deps: ["imagemagick"], ["netpbm"], []

    @abstractmethod
    def apply(self, image: Image, params: dict,
              context: EffectContext) -> EffectResult:
        """
        image:   PIL.Image (RGB/RGBA)
        params:  Resolved recipe params (ranges already rolled)
        context: Vision analysis, temp dir, RNG seed, source metadata
        Returns: EffectResult(image=PIL.Image, metadata=dict)
        """

    @abstractmethod
    def validate_params(self, params: dict) -> dict:
        """
        Validate and normalize params.
        Raise ConfigError with clear message on bad input.
        Auto-correct where sensible (clamp out-of-range, default missing optional).
        """
```

`EffectContext` carries shared state through the pipeline: Llama Vision analysis results, a temp directory for subprocess effects, the RNG seed for reproducibility, and source image metadata.

`EffectResult` returns the processed image plus a metadata dict (actual params used after range resolution, any interesting intermediate values) for provenance logging.

Effects that shell out to external tools (ImageMagick, NetPBM, ffmpeg, potrace, primitive) inherit from `SubprocessEffect`, which handles temp file creation/cleanup, execution timeouts, and stderr capture for debugging.

## Effects Capability Table

This table appears in the README to give a quick overview of what sparagmos can do.

| Effect | Era | What It Does | System Deps |
|--------|-----|-------------|-------------|
| `byte_corrupt` | 1980s+ | Flip/inject/replace raw bytes in image data, skip headers | None |
| `netpbm` | 1988 | Ancient Unix filters: moon craters, fractal planets, pixel spread | `netpbm` |
| `imagemagick` | 1990 | `-implode`, `-swirl`, `-fx` expressions, `-morphology`, `-distort` | `imagemagick` |
| `sonify` | 2000s | Import image as raw audio, apply DSP effects, export back | None |
| `format_roundtrip` | 2000s | Lossy conversion chains: bitmap → potrace vector → rasterize back | `potrace` |
| `pixel_sort` | 2010 | Sort pixel rows/columns by brightness, hue, or saturation | None |
| `datamosh` | 2010s | I-frame removal, motion vector swapping between images | `ffmpeg` |
| `channel_shift` | 2010s | Offset/swap/separate RGB channels, chromatic aberration | None |
| `dither` | 2010s | Floyd-Steinberg, Bayer, Atkinson + retro palettes (CGA, EGA, Game Boy) | None |
| `seam_carve` | 2010s | Content-aware resize, intentionally broken — melt faces, bend buildings | None |
| `crt_vhs` | 2010s | Scan lines, tracking errors, color bleeding, phosphor glow, horizontal jitter | None |
| `jpeg_destroy` | 2010s | Save at quality 1, reopen, repeat N times — generational loss as art | None |
| `primitive` | 2016 | Reconstruct with geometric shapes (triangles, ellipses) at low iteration | `primitive` |
| `deepdream` | 2015 | Amplify neural net patterns — dogs, eyes, pagodas emerge from noise | None (PyTorch) |
| `style_transfer` | 2015 | Apply style of one image to content of another (Gatys algorithm) | None (PyTorch) |
| `neural_doodle` | 2016 | Semantic style painting with rough masks → surreal photorealism | None (PyTorch) |
| `pix2pix` | 2016-17 | Image-to-image translation, domain transfer artifacts | None (PyTorch) |
| `pca_decompose` | — | Reconstruct image from only top/bottom N PCA components | None |
| `cellular` | — | Game of Life / Rule 110 on pixel brightness, run N generations | None |
| `fractal_blend` | — | Mandelbrot at coordinates derived from image histogram, blend | None |
| `spectral` | — | Treat image as spectrogram, process with audio DSP, render back | None |
| `inpaint` | 2020s | Mask regions (random or Llama-targeted), regenerate with small diffusion model | None (PyTorch) |

## Recipe Format

Recipes are YAML files in the `recipes/` directory. Each recipe defines a named pipeline of effects with parameters.

### Schema

```yaml
name: Human-Readable Recipe Name
description: >
  Multi-line description of what this recipe does and
  why these effects were chosen together. Used in docs
  and optionally in Slack posts.

# Whether to run Llama Vision analysis before processing.
# Effects can reference vision results via "vision" param values.
# Optional, defaults to false.
vision: false

effects:
  - type: effect_name          # Must match a registered effect's name
    params:
      param_name: value        # Fixed value — used as-is
      param_name: [min, max]   # Range — random value chosen per run
      param_name: "vision"     # Resolved from Llama Vision analysis
```

### Parameter Resolution

- **Fixed values** (e.g., `quality: 5`) — used as-is every run.
- **Ranges** (e.g., `quality: [1, 10]`) — a random value is chosen uniformly within the range each run. Integer ranges produce integers; float ranges produce floats.
- **`"vision"` values** — resolved from Llama Vision analysis. Requires `vision: true` at the recipe level. The specific meaning depends on the effect (e.g., `protect_regions: "vision"` in seam_carve means "protect the regions Llama identified as interesting").

### Example Recipe

```yaml
# recipes/dionysian-rite.yaml
name: Dionysian Rite
description: >
  Ritual dismemberment through neural hallucination and analog decay.
  The image is torn apart and rebuilt by forces that don't understand it.
  DeepDream injects phantom forms, channel shifting fractures color,
  seam carving melts structure, and JPEG compression buries the remains.

vision: true

effects:
  - type: deepdream
    params:
      layers: ["inception4a", "inception4b"]
      iterations: [5, 15]
      octave_scale: 1.4
      jitter: 32

  - type: channel_shift
    params:
      offset_r: [20, 80]
      offset_b: [-60, -20]

  - type: seam_carve
    params:
      scale_x: [0.5, 0.7]
      protect_regions: "vision"

  - type: jpeg_destroy
    params:
      quality: [1, 5]
      iterations: [5, 20]
```

### Recipe Documentation Requirements

Each recipe YAML includes a `description` field explaining the artistic intent. Additionally, `docs/recipes.md` contains:

- A guide on how to create new recipes
- The full recipe schema reference
- Per-effect parameter documentation (every param, its type, valid range, default, and what it does)
- Example recipes with commentary explaining effect ordering and parameter choices
- Tips on effect chaining (e.g., "put lossy compression last — it compounds everything before it")

## Vendoring Strategy

Older, unmaintained, or fragile dependencies are vendored into `sparagmos/vendor/` to ensure stability and allow modifications.

### Vendored (copied into repo, pinned, modifiable)

- **Pixel sorting** — various abandoned Python implementations
- **DeepDream** — single-file PyTorch implementation (not a real library)
- **Neural style transfer** — single-file Gatys algorithm implementation
- **Seam carving** — small Python implementation, some unmaintained
- **pix2pix / CycleGAN** — extracted inference-only code from old repos
- **Neural doodle** — dead project, last updated ~2017

### Installed Normally (massive, stable, actively maintained)

- Pillow, PyTorch, numpy, scipy, OpenCV — too large to vendor, reliably maintained
- slack-sdk, requests, huggingface-hub — stable APIs

### System Packages (wrapped via subprocess)

- ImageMagick — `apt-get install imagemagick` (CI), `brew install imagemagick` (local)
- NetPBM — `apt-get install netpbm` (CI), `brew install netpbm` (local)
- ffmpeg — `apt-get install ffmpeg` (CI), `brew install ffmpeg` (local)
- potrace — `apt-get install potrace` (CI), `brew install potrace` (local)
- primitive — Go binary, installed via `go install github.com/fogleman/primitive@latest` or pre-built

### Provenance

`sparagmos/vendor/README.md` documents each vendored dependency:

- Source URL / repository
- Version or commit hash
- Date vendored
- Modifications made (if any) and why
- Original license

## Slack Integration

### Source: #image-gen

- Scrape full channel history using cursor-based pagination (`conversations_history`)
- Extract messages with file attachments (filter to image MIME types)
- Pick a random image that hasn't been processed before (check against `state.json`)
- Download using `_download_with_auth()` pattern (manual redirect following to preserve Authorization header, same pattern as drawma scraper)
- Validate Content-Type to reject non-image responses

### Output: #img-junkyard

Single message via `files_upload_v2` with `initial_comment`:

```
⛧ Dionysian Rite
deepdream → channel_shift → seam_carve → jpeg_destroy
source: image by @username in #image-gen (2026-01-15)
```

The image is attached inline to this same message. No threads, no follow-up messages.

### Credentials

- `SLACK_BOT_TOKEN` — existing secret, same token used by other bots
- `HF_TOKEN` — existing secret, for Llama Vision via HF Inference API
- Slack app scopes needed: `channels:history`, `channels:read`, `files:read`, `files:write`, `chat:write`

## Llama Vision Integration

Used when a recipe sets `vision: true`. Calls Llama 3.2 Vision via the HF Inference API (free tier, existing `HF_TOKEN`).

The vision analysis returns a structured description of the image content: what objects are present, where they are spatially, any text, dominant colors, composition. This is parsed into an `EffectContext.vision` dict that effects can reference.

Effects use vision data for targeted destruction — for example:
- `seam_carve` with `protect_regions: "vision"` protects detected faces/objects (or inverts: specifically targets them)
- `inpaint` with `mask_target: "vision"` masks the most "interesting" region for regeneration
- `deepdream` with `focus_region: "vision"` concentrates hallucination on specific areas

Vision analysis is optional per-recipe. Recipes without `vision: true` skip the API call entirely.

## State Management

`state.json` tracks which images have been processed to avoid repeats:

```json
{
  "processed": [
    {
      "source_file_id": "F12345ABC",
      "source_date": "2026-01-15",
      "source_user": "U67890DEF",
      "recipe": "dionysian-rite",
      "effects": ["deepdream", "channel_shift", "seam_carve", "jpeg_destroy"],
      "processed_date": "2026-03-26",
      "posted_ts": "1711411200.000100"
    }
  ]
}
```

This file is committed to the repo (same pattern as muzzik-bot/state.json). The GitHub Actions workflow commits and pushes state changes after each run.

### Exhaustion Behavior

When all images in #image-gen have been processed at least once, the bot resets and allows re-processing — but with a different recipe than last time. The same image through a different recipe is a completely different piece. State tracks the `(file_id, recipe)` pair, not just `file_id`, so an image is only "used" for a specific recipe.

### Output Format

The processed image is saved as PNG. Some effects (like `jpeg_destroy`) operate on JPEG internally as part of the effect, but the final pipeline output is always PNG to avoid unintentional additional compression.

## CLI Interface

```
python -m sparagmos                          # Full daily run (random image, random recipe, post)
python -m sparagmos --recipe dionysian-rite  # Specific recipe
python -m sparagmos --input photo.jpg --output junked.png  # Local image, no Slack
python -m sparagmos --dry-run                # Process but don't post
python -m sparagmos --list-recipes           # List available recipes with descriptions
python -m sparagmos --list-effects           # List available effects with deps
python -m sparagmos --validate               # Validate all recipes against effect schemas
```

Standard conventions: `--dry-run` for safe testing, local I/O mode for development, validation command for CI.

## GitHub Actions Workflow

```yaml
name: Sparagmos

on:
  schedule:
    - cron: '0 12 * * *'    # Daily at noon UTC
  workflow_dispatch:
    inputs:
      recipe:
        description: 'Recipe name (leave empty for random)'
        default: ''

jobs:
  sparagmos:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y imagemagick netpbm ffmpeg potrace

      - name: Install primitive
        run: go install github.com/fogleman/primitive@latest

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run sparagmos
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          if [ -n "${{ inputs.recipe }}" ]; then
            python -m sparagmos --recipe "${{ inputs.recipe }}"
          else
            python -m sparagmos
          fi

      - name: Commit state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add state.json
          if git diff --cached --quiet; then
            echo "No state changes."
          else
            git commit -m "chore: update state ($(date -u +%Y-%m-%d)) [skip ci]"
            git push
          fi
```

## Testing Strategy

### Layer 1: Effect Unit Tests

Each effect module gets its own test file. Tests cover:

- **Valid params produce valid output** — apply with known params, verify output is a valid PIL.Image with reasonable dimensions
- **Param validation** — bad params raise `ConfigError` with clear messages, auto-correction works for fixable values
- **Edge cases** — tiny images (1x1, 10x10), grayscale input, RGBA input, very large images
- **Determinism** — same seed + same params = same output (for effects that use RNG)
- **System dep skipping** — effects requiring system tools (ImageMagick, NetPBM, etc.) are skipped with `pytest.mark.skipif` when deps aren't installed

### Layer 2: Recipe Validation Tests

- Load every YAML file in `recipes/` and validate against the recipe schema
- Verify each effect `type` references a registered effect
- Verify all params are valid for their effect (checked against `validate_params`)
- Verify `vision: true` recipes only use `"vision"` param values in effects that support them

### Layer 3: Integration Tests

- Run the full pipeline with test fixture images through each recipe
- Verify output is a valid image file
- Verify metadata/provenance is captured correctly
- Slack posting is mocked — verify the `files_upload_v2` call has the right shape (file + `initial_comment`)
- One integration test per recipe

### CI

Tests run on every push/PR. System deps installed in CI so subprocess-based effects are tested. Neural effects (DeepDream, style transfer) run on small test images to keep CI fast.

## README Documentation

The README includes:

1. **Overview** — what sparagmos is, the name's meaning, what it does
2. **Effects capability table** — the full table from this spec, showing every effect with its era, description, and system deps
3. **Quickstart** — install deps, run locally with `--input`/`--output`, run against Slack
4. **Recipe guide** — link to `docs/recipes.md` for the full reference
5. **Architecture** — brief overview of the pipeline and module structure
6. **Development** — how to add new effects, how to write recipes, running tests

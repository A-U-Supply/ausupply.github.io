# src/generator.py
from dataclasses import dataclass, field
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


NEON_PALETTE = ["#ff00ff", "#00ff00", "#00ffff", "#ffff00", "#ff0000", "#ff6600", "#ff0099"]
PASTEL_PALETTE = ["#ffb3ba", "#baffc9", "#bae1ff", "#ffffba", "#ffdfba"]
MONO_PALETTE = ["#000000", "#333333", "#666666", "#999999", "#cccccc"]

PALETTES = {
    "neon": NEON_PALETTE,
    "pastel": PASTEL_PALETTE,
    "mono": MONO_PALETTE,
}

FONTS = ["Comic Sans MS", "Courier New", "Arial", "Times New Roman", "Impact"]


@dataclass
class GeneratorConfig:
    seed: int | None = None
    max_rotation: int = 30
    color_palette: str = "neon"
    font_chaos: int = 5
    density: int = 5
    effects_enabled: list[str] = field(default_factory=lambda: ["shadows", "borders"])
    media_dir: Path | None = None


@dataclass
class TitleStyle:
    text: str
    left: float
    top: float
    rotation: int
    font_size: int
    color: str
    font_family: str
    text_shadow: str | None
    border: str | None
    z_index: int


def generate_chaos_styles(titles: list[str], config: GeneratorConfig) -> list[dict]:
    """Generate randomized styles for each title."""
    if config.seed is not None:
        random.seed(config.seed)

    palette = PALETTES.get(config.color_palette, NEON_PALETTE)
    available_fonts = FONTS[:config.font_chaos]

    styles = []
    for i, title in enumerate(titles):
        left = random.uniform(5, 85)
        top = random.uniform(5, 90)
        rotation = random.randint(-config.max_rotation, config.max_rotation)
        font_size = random.randint(12, 48)
        color = random.choice(palette)
        font_family = random.choice(available_fonts)

        text_shadow = None
        if "shadows" in config.effects_enabled and random.random() > 0.5:
            shadow_color = random.choice(palette)
            text_shadow = f"2px 2px 4px {shadow_color}"

        border = None
        if "borders" in config.effects_enabled and random.random() > 0.7:
            border_color = random.choice(palette)
            border = f"2px dotted {border_color}"

        styles.append({
            "text": title,
            "left": left,
            "top": top,
            "rotation": rotation,
            "font_size": font_size,
            "color": color,
            "font_family": font_family,
            "text_shadow": text_shadow,
            "border": border,
            "z_index": i,
        })

    return styles


def get_media_files(media_dir: Path | None) -> list[str]:
    """Get list of image/GIF files from media directory."""
    if media_dir is None or not media_dir.exists():
        return []

    extensions = {".gif", ".png", ".jpg", ".jpeg", ".webp"}
    return [f.name for f in media_dir.iterdir() if f.suffix.lower() in extensions]


def generate_html(
    titles: list[str],
    config: GeneratorConfig,
    output_path: Path,
    template_dir: Path | None = None,
) -> None:
    """Generate the chaotic HTML page."""
    if template_dir is None:
        template_dir = Path(__file__).parent / "templates"

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("chaos.html.j2")

    styles = generate_chaos_styles(titles, config)
    media_files = get_media_files(config.media_dir)

    # Generate random positions for media if present
    media_styles = []
    if media_files and config.seed is not None:
        random.seed(config.seed + 1000)  # Different seed for media
    for media_file in media_files:
        media_styles.append({
            "src": media_file,
            "left": random.uniform(0, 90),
            "top": random.uniform(0, 90),
            "rotation": random.randint(-20, 20),
            "width": random.randint(50, 200),
            "z_index": random.randint(0, len(titles)),
        })

    html = template.render(
        title_styles=styles,
        media_styles=media_styles,
        config=config,
    )

    output_path.write_text(html)

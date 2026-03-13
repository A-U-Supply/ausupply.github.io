"""Generate the interactive this-song-is-a-junkyard.html page from titles.json."""
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

COLORS = [
    "#ff0000", "#ff4400", "#ff8800", "#ffcc00", "#ffff00",
    "#88ff00", "#00ff00", "#00ff88", "#00ffff", "#0088ff",
    "#0000ff", "#4400ff", "#8800ff", "#ff00ff", "#ff0088",
    "#ffffff", "#ff6666", "#66ff66", "#6666ff", "#ffff66",
]

FONTS = [
    "'Comic Sans MS', cursive",
    "'Impact', sans-serif",
    "'Courier New', monospace",
    "'Arial Black', sans-serif",
    "'Georgia', serif",
    "'Trebuchet MS', sans-serif",
    "'Verdana', sans-serif",
    "'Papyrus', fantasy",
]


def _randomize_title(title: dict, index: int) -> dict:
    """Add random visual properties to a title for initial layout."""
    return {
        **title,
        "left": random.uniform(2, 85),
        "top": 120 + random.randint(0, 2400),
        "font_size": random.randint(14, 42),
        "color": random.choice(COLORS),
        "rotation": random.randint(-30, 30),
        "font_family": random.choice(FONTS),
        "z_index": index + 1,
    }


def generate_html(titles: list[dict]) -> str:
    """Render the song titles page from a list of title dicts."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("junkyard.html.j2")

    styled_titles = [_randomize_title(t, i) for i, t in enumerate(titles)]

    return template.render(titles=styled_titles)

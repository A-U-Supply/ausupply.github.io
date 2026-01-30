# src/cli.py
import argparse
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
import os

from src.slack_fetcher import fetch_messages, SlackConfig
from src.filter import filter_song_titles, FilterConfig
from src.generator import generate_html, GeneratorConfig
from src.cache import save_titles, load_titles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate chaotic geocities-style pages from Slack song titles"
    )

    parser.add_argument(
        "--channel-id",
        help="Slack channel ID (overrides .env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("songtitles.html"),
        help="Output HTML file path",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible chaos",
    )
    parser.add_argument(
        "--media-dir",
        type=Path,
        help="Directory of images/GIFs to scatter",
    )
    parser.add_argument(
        "--density",
        type=int,
        choices=range(1, 11),
        default=5,
        help="How packed/sparse (1-10)",
    )
    parser.add_argument(
        "--color-palette",
        choices=["neon", "pastel", "mono", "random"],
        default="neon",
        help="Color palette preset",
    )
    parser.add_argument(
        "--font-chaos",
        type=int,
        choices=range(1, 6),
        default=5,
        help="How many different fonts (1-5)",
    )
    parser.add_argument(
        "--max-rotation",
        type=int,
        default=30,
        help="Maximum rotation in degrees",
    )
    parser.add_argument(
        "--title-limit",
        type=int,
        default=500,
        help="Maximum titles to display",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Fetch & filter only, don't generate HTML",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Skip fetch, use cached titles",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Randomize all visual settings",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=Path("cache/titles.json"),
        help="Path to titles cache file",
    )

    return parser.parse_args()


def randomize_config(seed: int | None) -> dict:
    """Generate random config values."""
    if seed is not None:
        random.seed(seed)
    return {
        "color_palette": random.choice(["neon", "pastel", "mono"]),
        "font_chaos": random.randint(1, 5),
        "max_rotation": random.randint(10, 45),
        "density": random.randint(1, 10),
    }


def main() -> int:
    load_dotenv()
    args = parse_args()

    # Get Slack config from env or args
    token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = args.channel_id or os.getenv("SLACK_CHANNEL_ID")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")

    cache_path = args.cache_file

    # Fetch and filter (unless --generate-only)
    if not args.generate_only:
        if not token:
            print("Error: SLACK_BOT_TOKEN not set in .env", file=sys.stderr)
            return 1
        if not channel_id:
            print("Error: SLACK_CHANNEL_ID not set (use --channel-id or .env)", file=sys.stderr)
            return 1

        print(f"Fetching messages from Slack channel {channel_id}...")
        slack_config = SlackConfig(token=token, channel_id=channel_id)
        messages = fetch_messages(slack_config, limit=args.title_limit)
        print(f"Fetched {len(messages)} messages")

        print("Filtering for song titles with Ollama...")
        filter_config = FilterConfig(model=ollama_model)
        try:
            titles = filter_song_titles(messages, filter_config)
        except Exception as e:
            print(f"Error connecting to Ollama: {e}", file=sys.stderr)
            print("Make sure Ollama is running: ollama serve", file=sys.stderr)
            return 1

        print(f"Found {len(titles)} song titles")

        save_titles(titles, cache_path)
        print(f"Saved to cache: {cache_path}")

        if args.fetch_only:
            return 0
    else:
        titles = load_titles(cache_path)
        if not titles:
            print(f"Error: No cached titles found at {cache_path}", file=sys.stderr)
            print("Run without --generate-only first to fetch titles", file=sys.stderr)
            return 1
        print(f"Loaded {len(titles)} titles from cache")

    # Apply --random if set
    if args.random:
        random_settings = randomize_config(args.seed)
        args.color_palette = random_settings["color_palette"]
        args.font_chaos = random_settings["font_chaos"]
        args.max_rotation = random_settings["max_rotation"]
        args.density = random_settings["density"]
        print(f"Randomized settings: {random_settings}")

    # Generate HTML
    gen_config = GeneratorConfig(
        seed=args.seed,
        max_rotation=args.max_rotation,
        color_palette=args.color_palette,
        font_chaos=args.font_chaos,
        density=args.density,
        media_dir=args.media_dir,
    )

    print(f"Generating chaotic HTML...")
    generate_html(titles, gen_config, args.output)
    print(f"Generated: {args.output}")

    if args.seed:
        print(f"Seed: {args.seed} (use this to reproduce)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

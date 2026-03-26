"""Collage bot — fetches 4 random images from #image-gen, transforms, posts back."""
import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collage bot")
    parser.add_argument("--channel", default="image-gen")
    parser.add_argument("--output-dir", type=Path, default=Path("./collage-bot-output"))
    parser.add_argument("--no-post", action="store_true")
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN required", file=sys.stderr)
        sys.exit(1)

    from slack_fetcher import fetch_random_images
    from slack_poster import post_collages
    from transform import make_composites, apply_transform, blend_seams
    from PIL import Image

    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_dir = args.output_dir / "source"
    out_dir = args.output_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: fetch 4 random images
    logger.info(f"Fetching 4 images from #{args.channel}...")
    source_paths = fetch_random_images(token, args.channel, 4, source_dir)

    # Step 2+3: cut into quadrants and build 4 composite images
    logger.info("Building composites from quadrants...")
    source_images = [Image.open(p).convert("RGB") for p in source_paths]
    composites = make_composites(source_images)

    # Step 4: apply 1/4-3/4 transform to each composite
    output_paths = []
    for i, composite in enumerate(composites):
        transformed = apply_transform(composite)
        blended = blend_seams(transformed, strip_width=70)
        dest = out_dir / f"collage_{i + 1}.png"
        blended.save(dest)
        logger.info(f"Saved {dest.name}")
        output_paths.append(dest)

    if not args.no_post:
        post_collages(token, args.channel, output_paths)
        logger.info(f"Posted {len(output_paths)} collages to #{args.channel}")
    else:
        logger.info(f"Saved to {out_dir} (--no-post)")


if __name__ == "__main__":
    main()

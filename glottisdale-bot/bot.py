"""Glottisdale Slack bot — fetches videos, runs collage, posts results.

This is a thin wrapper around the glottisdale library. The library handles
the audio processing; this script handles Slack I/O.
"""

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add bot directory to path for glottisdale_slack package
sys.path.insert(0, str(Path(__file__).parent))

from glottisdale.collage import process
from glottisdale_slack.fetch import fetch_videos
from glottisdale_slack.post import post_results

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Glottisdale Slack bot")
    parser.add_argument("--source-channel", default="#sample-sale")
    parser.add_argument("--dest-channel", default="#glottisdale")
    parser.add_argument("--max-videos", type=int, default=5)
    parser.add_argument("--target-duration", type=float, default=30.0)
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium"])
    parser.add_argument("--aligner", default="auto",
                        choices=["auto", "default", "bfa"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-post", action="store_true")
    parser.add_argument("--output-dir", default="./glottisdale-output")
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
    args = build_parser().parse_args()

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable required", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        videos = fetch_videos(
            token=token,
            channel=args.source_channel,
            max_videos=args.max_videos,
            download_dir=Path(tmpdir),
        )

        if not videos:
            print("No videos found in channel", file=sys.stderr)
            sys.exit(1)

        result = process(
            input_paths=[v["path"] for v in videos],
            output_dir=args.output_dir,
            target_duration=args.target_duration,
            aligner=args.aligner,
            whisper_model=args.whisper_model,
            seed=args.seed,
        )

        logger.info(f"Processed {len(videos)} video(s), {len(result.clips)} clips")

        if not args.dry_run and not args.no_post:
            post_results(
                token=token,
                channel=args.dest_channel,
                result=result,
                sources=videos,
                output_dir=Path(args.output_dir),
            )


if __name__ == "__main__":
    main()

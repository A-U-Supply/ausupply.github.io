"""Glottisdale Slack bot — fetches videos, runs collage, posts results.

This is a thin wrapper that handles Slack I/O and invokes the glottisdale
Rust CLI binary for audio processing.
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add bot directory to path for glottisdale_slack package
sys.path.insert(0, str(Path(__file__).parent))

from glottisdale_slack.fetch import fetch_videos
from glottisdale_slack.post import post_results
from src.title_selector import select_title

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


def run_glottisdale_cli(video_paths: list[Path], args) -> dict:
    """Run the glottisdale CLI binary and return parsed output info."""
    cmd = [
        "glottisdale", "collage",
        *[str(p) for p in video_paths],
        "--output-dir", args.output_dir,
        "--target-duration", str(args.target_duration),
        "--whisper-model", args.whisper_model,
        "--aligner", args.aligner,
        "--phrase-pause", "200-400",
        "--sentence-pause", "500-800",
        "--syllables-per-word", "2-4",
    ]
    if args.seed is not None:
        cmd.extend(["--seed", str(args.seed)])

    logger.info(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    # Log CLI diagnostics (pitch normalization, syllable counts, etc.)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            logger.info(f"[glottisdale] {line}")

    if result.returncode != 0:
        raise RuntimeError(f"glottisdale CLI failed: {result.stderr.strip().splitlines()[-1]}")

    # Parse stdout for output path and clip count
    info = {"output": None, "clip_count": 0, "run_dir": None}
    for line in result.stdout.splitlines():
        if line.startswith("Output: "):
            info["output"] = Path(line.split("Output: ", 1)[1].strip())
            info["run_dir"] = info["output"].parent
        elif line.startswith("Selected "):
            try:
                info["clip_count"] = int(line.split()[1])
            except (IndexError, ValueError):
                pass

    if not info["output"] or not info["output"].exists():
        raise RuntimeError(f"CLI did not produce expected output. stdout: {result.stdout}")

    # Read manifest for per-source clip counts
    manifest_path = info["run_dir"] / "manifest.json"
    if manifest_path.exists():
        info["manifest"] = json.loads(manifest_path.read_text())

    logger.info(f"CLI output: {info['output']} ({info['clip_count']} clips)")
    return info


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

        # Select song title for labeling and seed derivation
        script_dir = Path(__file__).parent
        titles_path = script_dir / "../song-titles-bot/titles.json"
        used_path = script_dir / "used-song-titles.json"
        song_title_entry = select_title(titles_path, used_path)

        song_title = None
        if song_title_entry:
            song_title = song_title_entry["title"]
            logger.info(f"Song title: \"{song_title}\"")

            # Derive deterministic seed from title (if no explicit seed given)
            if args.seed is None:
                args.seed = int(hashlib.sha256(song_title.encode()).hexdigest()[:8], 16)
                logger.info(f"Derived seed from title: {args.seed}")

        info = run_glottisdale_cli(
            video_paths=[v["path"] for v in videos],
            args=args,
        )

        logger.info(f"Processed {len(videos)} video(s), {info['clip_count']} clips")

        if not args.dry_run and not args.no_post:
            # Count clips per source from manifest
            manifest = info.get("manifest", {})
            source_clip_counts = {}
            for clip in manifest.get("clips", []):
                source = clip.get("source", "")
                source_clip_counts[source] = source_clip_counts.get(source, 0) + 1

            post_results(
                token=token,
                channel=args.dest_channel,
                concatenated_path=info["output"],
                run_dir=info["run_dir"],
                clip_count=info["clip_count"],
                sources=videos,
                source_clip_counts=source_clip_counts,
                song_title=song_title,
            )


if __name__ == "__main__":
    main()

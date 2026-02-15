"""CLI entrypoint for glottisdale."""

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="glottisdale",
        description="Syllable-level audio collage tool",
    )

    # Positional: input files (optional — if omitted, uses Slack)
    parser.add_argument(
        "input_files", nargs="*", default=[],
        help="Local video/audio files. If omitted, fetches from Slack.",
    )

    # Core options
    parser.add_argument("--output-dir", default="./glottisdale-output",
                        help="Output directory (default: ./glottisdale-output)")
    parser.add_argument("--syllables-per-clip", type=int, default=1,
                        help="Syllables per clip (default: 1)")
    parser.add_argument("--target-duration", type=float, default=10.0,
                        help="Target total duration in seconds (default: 10)")
    parser.add_argument("--crossfade", type=float, default=10,
                        help="Crossfade between clips in ms (default: 10, 0=hard cut)")
    parser.add_argument("--padding", type=float, default=25,
                        help="Padding around syllable cuts in ms (default: 25)")
    parser.add_argument("--gap", default="50-200",
                        help="Silence between clips in ms: '0', '100', or '50-200' (default: 50-200)")
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--aligner", default="default",
                        help="Alignment backend (default: default)")
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed for reproducible output")

    # Slack options
    parser.add_argument("--source-channel", default="#sample-sale",
                        help="Slack channel to pull videos from (default: #sample-sale)")
    parser.add_argument("--dest-channel", default="#glottisdale",
                        help="Slack channel to post results to (default: #glottisdale)")
    parser.add_argument("--max-videos", type=int, default=5,
                        help="Max source videos from Slack (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Process but don't post to Slack")
    parser.add_argument("--no-post", action="store_true",
                        help="Skip Slack posting, just write to output-dir")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    args = parse_args(argv)

    if args.input_files:
        # Local mode
        from glottisdale import process

        input_paths = [Path(f) for f in args.input_files]
        for p in input_paths:
            if not p.exists():
                print(f"Error: file not found: {p}", file=sys.stderr)
                sys.exit(1)

        result = process(
            input_paths=input_paths,
            output_dir=args.output_dir,
            syllables_per_clip=args.syllables_per_clip,
            target_duration=args.target_duration,
            crossfade_ms=args.crossfade,
            padding_ms=args.padding,
            gap=args.gap,
            aligner=args.aligner,
            whisper_model=args.whisper_model,
            seed=args.seed,
        )

        # Print summary to stdout
        print(f"Processed {len(args.input_files)} source file(s)")
        print(f"Transcript: {result.transcript}")
        print(f"Selected {len(result.clips)} clips")
        print(f"Output:")
        for clip in result.clips:
            print(f"  {clip.output_path.name}")
        print(f"  {result.concatenated.name}")
        print(f"  clips.zip")
    else:
        # Slack mode
        try:
            from glottisdale_slack.fetch import fetch_videos
            from glottisdale_slack.post import post_results
        except ImportError:
            print("Error: Slack mode requires slack extras: pip install glottisdale[slack]",
                  file=sys.stderr)
            sys.exit(1)

        import os
        import tempfile

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

            from glottisdale import process

            result = process(
                input_paths=[v["path"] for v in videos],
                output_dir=args.output_dir,
                syllables_per_clip=args.syllables_per_clip,
                target_duration=args.target_duration,
                crossfade_ms=args.crossfade,
                padding_ms=args.padding,
                gap=args.gap,
                aligner=args.aligner,
                whisper_model=args.whisper_model,
                seed=args.seed,
            )

            # Print summary
            print(f"Processed {len(videos)} source video(s), extracted {len(result.clips)} syllable clips")
            print("Sources:")
            for v in videos:
                syl_count = len([c for c in result.clips if c.source == Path(v["path"]).stem])
                link = v.get("permalink", "")
                print(f"  - {Path(v['path']).name} ({syl_count} syllables) {link}")
            print(f"Output:")
            print(f"  {result.concatenated}")
            print(f"  clips.zip")

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

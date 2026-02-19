"""CLI entrypoint for glottisdale."""

import argparse
import logging
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

    # Core options — prosodic grouping
    parser.add_argument("--output-dir", default="./glottisdale-output",
                        help="Output directory (default: ./glottisdale-output)")
    parser.add_argument("--syllables-per-word", default="1-4",
                        help="Syllables per word: '3', or '1-4' for variable (default: 1-4)")
    parser.add_argument("--syllables-per-clip", default=None,
                        help=argparse.SUPPRESS)  # deprecated alias
    parser.add_argument("--target-duration", type=float, default=30.0,
                        help="Target total duration in seconds (default: 30)")
    parser.add_argument("--crossfade", type=float, default=30,
                        help="Crossfade between syllables in a word, ms (default: 30, 0=hard cut)")
    parser.add_argument("--padding", type=float, default=25,
                        help="Padding around syllable cuts in ms (default: 25)")
    parser.add_argument("--words-per-phrase", default="3-5",
                        help="Words per phrase: '4', or '3-5' (default: 3-5)")
    parser.add_argument("--phrases-per-sentence", default="2-3",
                        help="Phrases per sentence group: '2', or '2-3' (default: 2-3)")
    parser.add_argument("--phrase-pause", default="400-700",
                        help="Silence between phrases in ms: '500' or '400-700' (default: 400-700)")
    parser.add_argument("--sentence-pause", default="800-1200",
                        help="Silence between sentences in ms: '1000' or '800-1200' (default: 800-1200)")
    parser.add_argument("--word-crossfade", type=float, default=50,
                        help="Crossfade between words in a phrase, ms (default: 50)")
    parser.add_argument("--gap", default=None,
                        help=argparse.SUPPRESS)  # deprecated alias for --phrase-pause
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--aligner", default="auto",
                        choices=["auto", "default", "bfa"],
                        help="Alignment backend: auto (try BFA, fallback to default), "
                             "default (proportional), bfa (forced alignment) (default: auto)")
    parser.add_argument("--bfa-device", default="cpu",
                        choices=["cpu", "cuda"],
                        help="Device for BFA model inference (default: cpu)")
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

    args = parser.parse_args(argv)

    # Backward compat: --syllables-per-clip -> --syllables-per-word
    if args.syllables_per_clip is not None:
        print("Warning: --syllables-per-clip is deprecated, use --syllables-per-word",
              file=sys.stderr)
        args.syllables_per_word = args.syllables_per_clip
    # Backward compat: --gap -> --phrase-pause
    if args.gap is not None:
        print("Warning: --gap is deprecated, use --phrase-pause", file=sys.stderr)
        args.phrase_pause = args.gap

    return args


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
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
            syllables_per_clip=args.syllables_per_word,
            target_duration=args.target_duration,
            crossfade_ms=args.crossfade,
            padding_ms=args.padding,
            words_per_phrase=args.words_per_phrase,
            phrases_per_sentence=args.phrases_per_sentence,
            phrase_pause=args.phrase_pause,
            sentence_pause=args.sentence_pause,
            word_crossfade_ms=args.word_crossfade,
            aligner=args.aligner,
            whisper_model=args.whisper_model,
            bfa_device=args.bfa_device,
            seed=args.seed,
            noise_level_db=args.noise_level,
            room_tone=args.room_tone,
            pitch_normalize=args.pitch_normalize,
            pitch_range=args.pitch_range,
            breaths=args.breaths,
            breath_probability=args.breath_probability,
            volume_normalize=args.volume_normalize,
            prosodic_dynamics=args.prosodic_dynamics,
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
                syllables_per_clip=args.syllables_per_word,
                target_duration=args.target_duration,
                crossfade_ms=args.crossfade,
                padding_ms=args.padding,
                words_per_phrase=args.words_per_phrase,
                phrases_per_sentence=args.phrases_per_sentence,
                phrase_pause=args.phrase_pause,
                sentence_pause=args.sentence_pause,
                word_crossfade_ms=args.word_crossfade,
                aligner=args.aligner,
                whisper_model=args.whisper_model,
                bfa_device=args.bfa_device,
                seed=args.seed,
                noise_level_db=args.noise_level,
                room_tone=args.room_tone,
                pitch_normalize=args.pitch_normalize,
                pitch_range=args.pitch_range,
                breaths=args.breaths,
                breath_probability=args.breath_probability,
                volume_normalize=args.volume_normalize,
                prosodic_dynamics=args.prosodic_dynamics,
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

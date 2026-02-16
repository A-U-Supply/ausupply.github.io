"""Hymnal Gargler CLI — syllable-level vocal collage over MIDI melodies."""
import argparse
import logging
import os
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Hymnal Gargler — syllable-level vocal collage over MIDI melodies",
    )

    # Local mode flags
    parser.add_argument(
        "--midi", type=Path, default=None,
        help="Directory containing MIDI files (local mode)",
    )
    parser.add_argument(
        "--audio", type=Path, nargs="+", default=None,
        help="Audio/video files to process (local mode, can be multiple)",
    )

    # Output
    parser.add_argument(
        "--output-dir", type=Path, default=Path("./hymnal-gargler-output"),
        help="Output directory (default: ./hymnal-gargler-output)",
    )

    # Pipeline parameters
    parser.add_argument(
        "--target-duration", type=float, default=40,
        help="Target duration in seconds (default: 40)",
    )
    parser.add_argument(
        "--max-videos", type=int, default=5,
        help="Max #sample-sale videos to fetch (default: 5)",
    )
    parser.add_argument(
        "--whisper-model", type=str, default="base",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size (default: base)",
    )

    # Audio effects toggles
    parser.add_argument(
        "--vibrato", "--no-vibrato", action=argparse.BooleanOptionalAction,
        default=True,
        help="Toggle vibrato (default: enabled)",
    )
    parser.add_argument(
        "--chorus", "--no-chorus", action=argparse.BooleanOptionalAction,
        default=True,
        help="Toggle chorus (default: enabled)",
    )

    # Drift
    parser.add_argument(
        "--drift-range", type=float, default=2.0,
        help="Max semitone drift from melody (default: 2.0)",
    )

    # Run modes
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip Slack posting",
    )
    parser.add_argument(
        "--no-post", action="store_true",
        help="Local only, no Slack",
    )

    # Reproducibility
    parser.add_argument(
        "--seed", type=int, default=None,
        help="RNG seed for reproducibility",
    )

    # Slack channels
    parser.add_argument(
        "--source-channel", type=str, default="midieval",
        help="Slack channel for MIDI source (default: midieval)",
    )
    parser.add_argument(
        "--video-channel", type=str, default="sample-sale",
        help="Slack channel for videos (default: sample-sale)",
    )
    parser.add_argument(
        "--dest-channel", type=str, default="glottisdale",
        help="Slack channel for posting results (default: glottisdale)",
    )

    return parser


def _validate_local_args(args: argparse.Namespace) -> None:
    """Validate that local mode has both --midi and --audio."""
    if args.midi and not args.audio:
        print("Error: --audio is required when --midi is provided", file=sys.stderr)
        sys.exit(1)
    if args.audio and not args.midi:
        print("Error: --midi is required when --audio is provided", file=sys.stderr)
        sys.exit(1)


def _run_local(args: argparse.Namespace) -> None:
    """Run the pipeline in local mode with provided MIDI and audio files."""
    from midi_parser import parse_midi
    from syllable_prep import prepare_syllables
    from vocal_mapper import plan_note_mapping, render_vocal_track
    from mixer import mix_tracks

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Load MIDI - parse the melody track
    melody_path = args.midi / "melody.mid"
    logger.info(f"Parsing MIDI: {melody_path}")
    track = parse_midi(melody_path)
    logger.info(f"Melody: {len(track.notes)} notes, {track.tempo} BPM, {track.total_duration:.1f}s")

    # Prepare syllables from audio files
    logger.info(f"Preparing syllables from {len(args.audio)} audio file(s)")
    syllables = prepare_syllables(args.audio, work_dir, args.whisper_model)
    logger.info(f"Prepared {len(syllables)} syllables")

    # Compute median F0 from syllables
    voiced_f0 = [s.f0 for s in syllables if s.f0 and s.f0 > 0]
    median_f0 = median(voiced_f0) if voiced_f0 else 220.0
    logger.info(f"Median F0: {median_f0:.1f} Hz")

    # Plan note mapping
    mappings = plan_note_mapping(
        track.notes, len(syllables),
        seed=args.seed, drift_range=args.drift_range,
    )
    logger.info(f"Planned {len(mappings)} note mappings")

    # Render vocal track
    logger.info("Rendering vocal track")
    acappella = render_vocal_track(
        mappings, syllables, work_dir, median_f0, args.target_duration,
    )
    logger.info(f"Vocal track: {acappella}")

    # Mix with backing
    logger.info("Mixing tracks")
    full_mix, acappella_out = mix_tracks(acappella, args.midi, output_dir)
    logger.info(f"Output: {full_mix}")
    logger.info(f"A cappella: {acappella_out}")


def _run_slack(args: argparse.Namespace) -> None:
    """Run the pipeline in Slack mode — fetch MIDI and videos, process, post."""
    from midi_parser import parse_midi
    from syllable_prep import prepare_syllables
    from vocal_mapper import plan_note_mapping, render_vocal_track
    from mixer import mix_tracks
    from slack_fetcher import fetch_latest_midi, fetch_videos
    from extender import extend_midi
    from slack_poster import post_results

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN required for Slack mode", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Fetch MIDI from #midieval
    midi_dir = work_dir / "midi"
    logger.info(f"Fetching MIDI from #{args.source_channel}")
    metadata, permalink = fetch_latest_midi(token, midi_dir)
    if not metadata:
        print("No MIDI found in #midieval", file=sys.stderr)
        sys.exit(1)

    logger.info(f"Found: {metadata.get('scale')} in {metadata.get('root')} ({metadata.get('tempo')} BPM)")

    # Extend MIDI to target duration
    extended_dir = work_dir / "extended"
    logger.info(f"Extending MIDI to ~{args.target_duration}s")
    extend_midi(
        melody_path=midi_dir / "melody.mid",
        drums_path=midi_dir / "drums.mid",
        bass_path=midi_dir / "bass.mid",
        chords_path=midi_dir / "chords.mid",
        output_dir=extended_dir,
        target_duration=args.target_duration,
        scale=metadata.get("scale", "Major"),
        root=metadata.get("root", "C"),
        tempo=metadata.get("tempo", 120),
        chords=metadata.get("chords"),
        temperature=metadata.get("temperature", 1.0),
    )

    # Fetch videos from #sample-sale
    video_dir = work_dir / "videos"
    logger.info(f"Fetching up to {args.max_videos} videos from #{args.video_channel}")
    fetch_videos(token, video_dir, args.max_videos, args.video_channel)

    # Parse extended melody
    track = parse_midi(extended_dir / "melody.mid")
    logger.info(f"Extended melody: {len(track.notes)} notes, {track.total_duration:.1f}s")

    # Prepare syllables from video files
    video_files = list(video_dir.glob("*"))
    logger.info(f"Preparing syllables from {len(video_files)} video(s)")
    syllables = prepare_syllables(video_files, work_dir, args.whisper_model)
    logger.info(f"Prepared {len(syllables)} syllables")

    # Compute median F0
    voiced_f0 = [s.f0 for s in syllables if s.f0 and s.f0 > 0]
    median_f0 = median(voiced_f0) if voiced_f0 else 220.0
    logger.info(f"Median F0: {median_f0:.1f} Hz")

    # Plan note mapping
    mappings = plan_note_mapping(
        track.notes, len(syllables),
        seed=args.seed, drift_range=args.drift_range,
    )
    logger.info(f"Planned {len(mappings)} note mappings")

    # Render vocal track
    logger.info("Rendering vocal track")
    acappella = render_vocal_track(
        mappings, syllables, work_dir, median_f0, args.target_duration,
    )

    # Mix with backing (use extended MIDI dir)
    logger.info("Mixing tracks")
    full_mix, acappella_out = mix_tracks(acappella, extended_dir, output_dir)
    logger.info(f"Output: {full_mix}")
    logger.info(f"A cappella: {acappella_out}")

    # Post results (unless --dry-run or --no-post)
    if not args.dry_run and not args.no_post:
        logger.info(f"Posting results to #{args.dest_channel}")
        post_results(token, args.dest_channel, full_mix, acappella_out, metadata, permalink)
    else:
        logger.info("Skipping Slack post (--dry-run or --no-post)")


def main():
    """Entry point for the Hymnal Gargler CLI."""
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    _validate_local_args(args)

    is_local = args.midi is not None and args.audio is not None

    try:
        if is_local:
            logger.info("Running in local mode")
            _run_local(args)
        else:
            logger.info("Running in Slack mode")
            _run_slack(args)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

    logger.info("Done!")


if __name__ == "__main__":
    main()

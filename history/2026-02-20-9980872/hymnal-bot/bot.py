"""Hymnal Gargler Slack bot — fetches MIDI + videos, runs sing pipeline, posts results.

This is a thin wrapper around the glottisdale library. The library handles
audio processing and vocal MIDI mapping; this script handles Slack I/O and
Magenta.js MIDI extension.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from statistics import median

# Add bot directory to path for local modules
sys.path.insert(0, str(Path(__file__).parent))

from glottisdale.sing.midi_parser import parse_midi
from glottisdale.sing.syllable_prep import prepare_syllables
from glottisdale.sing.vocal_mapper import plan_note_mapping, render_vocal_track
from glottisdale.sing.mixer import mix_tracks

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hymnal Gargler — vocal MIDI mapping bot")

    # Local mode
    parser.add_argument("--midi", type=Path, default=None,
                        help="Directory with MIDI files (local mode)")
    parser.add_argument("--audio", type=Path, nargs="+", default=None,
                        help="Audio/video files (local mode)")

    # Shared
    parser.add_argument("--output-dir", type=Path, default=Path("./hymnal-gargler-output"))
    parser.add_argument("--target-duration", type=float, default=40)
    parser.add_argument("--max-videos", type=int, default=5)
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium"])
    parser.add_argument("--vibrato", "--no-vibrato",
                        action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--chorus", "--no-chorus",
                        action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--drift-range", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-post", action="store_true")

    # Slack channels
    parser.add_argument("--source-channel", default="midieval")
    parser.add_argument("--video-channel", default="sample-sale")
    parser.add_argument("--dest-channel", default="glottisdale")

    return parser


def _run_local(args):
    """Run in local mode with provided MIDI and audio files."""
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    track = parse_midi(args.midi / "melody.mid")
    logger.info(f"Melody: {len(track.notes)} notes, {track.tempo} BPM, {track.total_duration:.1f}s")

    syllables = prepare_syllables(args.audio, work_dir, args.whisper_model)
    logger.info(f"Prepared {len(syllables)} syllables")

    voiced_f0 = [s.f0 for s in syllables if s.f0 and s.f0 > 0]
    median_f0 = median(voiced_f0) if voiced_f0 else 220.0

    mappings = plan_note_mapping(
        track.notes, len(syllables),
        seed=args.seed, drift_range=args.drift_range,
    )

    acappella = render_vocal_track(mappings, syllables, work_dir, median_f0, args.target_duration)
    full_mix, acappella_out = mix_tracks(acappella, args.midi, output_dir)
    logger.info(f"Output: {full_mix}, A cappella: {acappella_out}")


def _run_slack(args):
    """Run in Slack mode — fetch MIDI, extend, fetch videos, process, post."""
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
    metadata, permalink = fetch_latest_midi(token, midi_dir)
    if not metadata:
        print("No MIDI found in #midieval", file=sys.stderr)
        sys.exit(1)

    logger.info(f"Found: {metadata.get('scale')} in {metadata.get('root')} ({metadata.get('tempo')} BPM)")

    # Extend MIDI to target duration
    extended_dir = work_dir / "extended"
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
    video_dir.mkdir(parents=True, exist_ok=True)
    fetch_videos(token, video_dir, args.max_videos, args.video_channel)

    # Parse extended melody
    track = parse_midi(extended_dir / "melody.mid")
    logger.info(f"Extended melody: {len(track.notes)} notes, {track.total_duration:.1f}s")

    # Prepare syllables
    video_files = list(video_dir.glob("*"))
    syllables = prepare_syllables(video_files, work_dir, args.whisper_model)
    logger.info(f"Prepared {len(syllables)} syllables")

    voiced_f0 = [s.f0 for s in syllables if s.f0 and s.f0 > 0]
    median_f0 = median(voiced_f0) if voiced_f0 else 220.0

    mappings = plan_note_mapping(
        track.notes, len(syllables),
        seed=args.seed, drift_range=args.drift_range,
    )

    acappella = render_vocal_track(mappings, syllables, work_dir, median_f0, args.target_duration)
    full_mix, acappella_out = mix_tracks(acappella, extended_dir, output_dir)
    logger.info(f"Output: {full_mix}, A cappella: {acappella_out}")

    if not args.dry_run and not args.no_post:
        post_results(token, args.dest_channel, full_mix, acappella_out, metadata, permalink)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()

    if args.midi and not args.audio:
        print("Error: --audio is required when --midi is provided", file=sys.stderr)
        sys.exit(1)
    if args.audio and not args.midi:
        print("Error: --midi is required when --audio is provided", file=sys.stderr)
        sys.exit(1)

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

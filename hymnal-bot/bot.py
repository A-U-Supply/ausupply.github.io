"""Hymnal Gargler Slack bot — fetches MIDI + videos, runs sing pipeline, posts results.

This is a thin wrapper that handles Slack I/O and MIDI extension, then invokes
the glottisdale Rust CLI binary for vocal MIDI mapping.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add bot directory to path for local modules
sys.path.insert(0, str(Path(__file__).parent))

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


def run_glottisdale_sing(audio_paths: list[Path], midi_dir: Path, args) -> dict:
    """Run the glottisdale sing CLI and return parsed output info."""
    cmd = [
        "glottisdale", "sing",
        *[str(p) for p in audio_paths],
        "--midi", str(midi_dir),
        "--output-dir", str(args.output_dir),
        "--target-duration", str(args.target_duration),
        "--whisper-model", args.whisper_model,
        "--drift-range", str(args.drift_range),
    ]
    if args.seed is not None:
        cmd.extend(["--seed", str(args.seed)])
    if not args.vibrato:
        cmd.append("--no-vibrato")
    if not args.chorus:
        cmd.append("--no-chorus")

    logger.info(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"CLI stderr: {result.stderr}")
        raise RuntimeError(f"glottisdale sing failed: {result.stderr.strip().splitlines()[-1]}")

    info = {"full_mix": None, "acappella": None}
    for line in result.stdout.splitlines():
        if line.startswith("Output: "):
            info["full_mix"] = Path(line.split("Output: ", 1)[1].strip())
        elif line.startswith("A cappella: "):
            info["acappella"] = Path(line.split("A cappella: ", 1)[1].strip())

    if not info["full_mix"] or not info["full_mix"].exists():
        raise RuntimeError(f"CLI did not produce expected output. stdout: {result.stdout}")

    logger.info(f"Output: {info['full_mix']}, A cappella: {info['acappella']}")
    return info


def _run_local(args):
    """Run in local mode with provided MIDI and audio files."""
    args.output_dir.mkdir(parents=True, exist_ok=True)

    info = run_glottisdale_sing(
        audio_paths=args.audio,
        midi_dir=args.midi,
        args=args,
    )
    logger.info(f"Output: {info['full_mix']}, A cappella: {info['acappella']}")


def _run_slack(args):
    """Run in Slack mode — fetch MIDI, extend, fetch videos, process, post."""
    from slack_fetcher import fetch_latest_midi, fetch_videos
    from extender import extend_midi
    from slack_poster import post_results

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN required for Slack mode", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = args.output_dir / "work"
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

    video_files = list(video_dir.glob("*"))
    if not video_files:
        print("No videos downloaded", file=sys.stderr)
        sys.exit(1)

    # Run glottisdale sing
    info = run_glottisdale_sing(
        audio_paths=video_files,
        midi_dir=extended_dir,
        args=args,
    )

    if not args.dry_run and not args.no_post:
        post_results(token, args.dest_channel, info["full_mix"], info["acappella"], metadata, permalink)


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

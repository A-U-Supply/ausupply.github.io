#!/usr/bin/env python3
"""Daily MIDI Bot - Generates 4 MIDI files and posts to Slack."""

import argparse
import importlib.util
import json
import logging
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

# Import local midi-bot modules first (before any sys.path manipulation)
from src.config import load_config, merge_cli_args
from src.generator import (
    generate_music_params, load_scales, load_instruments
)
from src.slack_poster import post_midi_to_slack


# Import scraper/sampler from surreal-prompt-bot using importlib.util
# to avoid namespace collision with midi-bot's own src/ package.
def _import_from_surreal_prompt_bot(module_name):
    """Import a module from surreal-prompt-bot/src/ without polluting sys.path."""
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "surreal-prompt-bot" / "src" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"spb_{module_name}", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_scraper = _import_from_surreal_prompt_bot("scraper")
_sampler = _import_from_surreal_prompt_bot("sampler")
scrape_all_sources = _scraper.scrape_all_sources
load_inspirations = _sampler.load_inspirations
sample_inspirations = _sampler.sample_inspirations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_midi_generation(params: dict, output_dir: Path) -> bool:
    """Run the Node.js MIDI generator as a subprocess."""
    script_path = Path(__file__).parent / "generate_midi.js"

    # Add scale_intervals to params for the Node.js script
    scales = load_scales(Path(__file__).parent / "scales.json")
    scale_entry = next((s for s in scales if s["name"] == params["scale"]), None)
    if not scale_entry:
        logger.error(f"Scale not found: {params['scale']}")
        return False

    node_params = {**params, "scale_intervals": scale_entry["intervals"]}

    try:
        result = subprocess.run(
            ["node", str(script_path), str(output_dir)],
            input=json.dumps(node_params),
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent),
        )
        logger.info(f"Node.js stdout: {result.stdout}")
        if result.returncode != 0:
            logger.error(f"Node.js stderr: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("MIDI generation timed out (5 min)")
        return False
    except Exception as e:
        logger.error(f"Failed to run Node.js generator: {e}")
        return False


def run_bot(args) -> int:
    """Main bot logic. Returns exit code."""
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config
    config = load_config(config_path)
    config = merge_cli_args(config, args)

    # Get API keys
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        logger.error("HF_TOKEN environment variable not set")
        return 1

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token and not args.dry_run:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    # Scrape headlines (reusing surreal-prompt-bot scraper)
    logger.info(f"Scraping headlines from {len(config['sources'])} sources...")
    headlines = scrape_all_sources(config["sources"])
    if not headlines:
        logger.error("No headlines scraped from any source")
        return 1

    max_headlines = config["prompt"]["max_headlines"]
    if len(headlines) > max_headlines:
        headlines = random.sample(headlines, max_headlines)
    logger.info(f"Using {len(headlines)} headlines")

    # Sample musical inspirations
    inspirations = []
    if config["inspirations"]["pick_count"] > 0:
        insp_path = script_dir / config["inspirations"]["file"]
        all_inspirations = load_inspirations(insp_path)
        inspirations = sample_inspirations(
            all_inspirations, config["inspirations"]["pick_count"]
        )
        logger.info(f"Using inspirations: {inspirations}")

    # Load scales + instruments databases
    scales = load_scales(script_dir / "scales.json")
    instruments = load_instruments(script_dir / "instruments.json")

    # Generate music parameters via LLM
    logger.info("Generating music parameters via LLM...")
    params = generate_music_params(
        headlines=headlines,
        inspirations=inspirations,
        scales=scales,
        instruments=instruments,
        model=config["prompt"]["model"],
        temperature=config["prompt"]["temperature"],
        api_key=hf_token,
    )
    logger.info(f"Music params: {json.dumps(params, indent=2)}")

    # Generate MIDI files
    with tempfile.TemporaryDirectory() as midi_dir:
        midi_path = Path(midi_dir)
        logger.info("Generating MIDI files...")

        if not run_midi_generation(params, midi_path):
            logger.error("MIDI generation failed")
            return 1

        # Verify all 4 files exist
        for track in ["melody", "drums", "bass", "chords"]:
            if not (midi_path / f"{track}.mid").exists():
                logger.error(f"Missing generated file: {track}.mid")
                return 1

        logger.info("All 4 MIDI files generated successfully")

        if args.dry_run:
            logger.info("Dry run - not posting to Slack")
            # Copy files to a visible location for inspection
            import shutil
            dry_run_dir = script_dir / "dry-run-output"
            dry_run_dir.mkdir(exist_ok=True)
            for f in midi_path.glob("*.mid"):
                shutil.copy2(f, dry_run_dir / f.name)
            logger.info(f"MIDI files saved to {dry_run_dir}")
            return 0

        # Post to Slack
        channel = config["slack"]["channel"]
        logger.info(f"Posting to Slack channel {channel}...")
        if post_midi_to_slack(params, instruments, midi_path, channel, slack_token):
            logger.info("Successfully posted to Slack!")
            return 0
        else:
            logger.error("Failed to post to Slack")
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="Generate daily MIDI files and post to Slack"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate MIDI but don't post to Slack")
    parser.add_argument("--channel", help="Override Slack channel")
    parser.add_argument("--temperature", type=float, help="LLM temperature")
    parser.add_argument("--sources", help="Comma-separated news sources")
    parser.add_argument("--no-inspirations", action="store_true")
    parser.add_argument("--config", default="config.yaml")

    args = parser.parse_args()
    return run_bot(args)


if __name__ == "__main__":
    sys.exit(main())

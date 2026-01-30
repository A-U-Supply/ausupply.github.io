#!/usr/bin/env python3
"""Surreal Prompt Bot - Daily surrealist drawing prompts from news headlines."""

import argparse
import logging
import os
import random
import sys
from pathlib import Path

from src.config import load_config, merge_cli_args
from src.scraper import scrape_all_sources
from src.sampler import load_inspirations, sample_inspirations
from src.generator import generate_prompt
from src.slack_poster import post_to_slack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_bot(args) -> int:
    """Main bot logic. Returns exit code."""
    # Load config
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config
    config = load_config(config_path)
    config = merge_cli_args(config, args)

    # Get API keys from environment
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("GROQ_API_KEY environment variable not set")
        return 1

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token and not args.dry_run:
        logger.error("SLACK_BOT_TOKEN environment variable not set")
        return 1

    # Scrape headlines
    logger.info(f"Scraping headlines from {len(config['sources'])} sources...")
    headlines = scrape_all_sources(config["sources"])

    if not headlines:
        logger.error("No headlines scraped from any source")
        return 1

    # Pick random subset of headlines
    max_headlines = config["prompt"]["max_headlines"]
    if len(headlines) > max_headlines:
        headlines = random.sample(headlines, max_headlines)

    logger.info(f"Using {len(headlines)} headlines")

    # Load and sample inspirations
    inspirations = []
    if config["inspirations"]["pick_count"] > 0:
        insp_path = script_dir / config["inspirations"]["file"]
        all_inspirations = load_inspirations(insp_path)
        inspirations = sample_inspirations(
            all_inspirations,
            config["inspirations"]["pick_count"]
        )
        logger.info(f"Using inspirations: {inspirations}")

    # Generate prompt
    logger.info("Generating surreal prompt...")
    prompt = generate_prompt(
        headlines=headlines,
        inspirations=inspirations,
        model=config["prompt"]["model"],
        temperature=config["prompt"]["temperature"],
        api_key=groq_api_key,
    )

    print(f"\n{'='*60}")
    print(f"Generated prompt:\n{prompt}")
    print(f"{'='*60}\n")

    # Post to Slack (unless dry run)
    if args.dry_run:
        logger.info("Dry run - not posting to Slack")
        return 0

    channel = config["slack"]["channel"]
    logger.info(f"Posting to Slack channel {channel}...")

    if post_to_slack(prompt, channel, slack_token):
        logger.info("Successfully posted to Slack!")
        return 0
    else:
        logger.error("Failed to post to Slack")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Generate surreal drawing prompts from news headlines"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate prompt but don't post to Slack"
    )
    parser.add_argument(
        "--channel",
        help="Override Slack channel (default: #drawma)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="LLM temperature 0.0-2.0 (default: 1.0)"
    )
    parser.add_argument(
        "--sources",
        help="Comma-separated list of news sources"
    )
    parser.add_argument(
        "--no-inspirations",
        action="store_true",
        help="Skip inspiration file"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Config file path (default: config.yaml)"
    )

    args = parser.parse_args()
    return run_bot(args)


if __name__ == "__main__":
    sys.exit(main())

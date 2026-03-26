#!/usr/bin/env python3
"""Song Titles Bot — scrape, filter, save, generate HTML."""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from huggingface_hub import InferenceClient
from slack_sdk import WebClient

from src.slack_scraper import fetch_new_messages
from src.filter import classify_messages
from src.html_generator import generate_html
from src.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_bot(
    titles_path: Path,
    html_output_path: Path,
    channel_name: str,
    hf_token: str,
    slack_token: str,
    model: str,
) -> int:
    """Main bot logic. Returns exit code."""
    # Load existing titles
    if titles_path.exists():
        existing = json.loads(titles_path.read_text())
    else:
        existing = []
    logger.info(f"Loaded {len(existing)} existing titles")

    # Find latest known timestamp for incremental fetching
    known_ids = {t["id"] for t in existing}
    latest_ts = None
    for t in existing:
        if t["id"] and not t["id"].startswith("legacy-"):
            if latest_ts is None or float(t["id"]) > float(latest_ts):
                latest_ts = t["id"]

    # Scrape new messages from Slack
    client = WebClient(token=slack_token)
    new_messages = fetch_new_messages(client, channel_name=channel_name, after_ts=latest_ts)
    logger.info(f"Fetched {len(new_messages)} new messages")

    # Filter for song titles
    if new_messages:
        hf_client = InferenceClient(token=hf_token)
        filtered = classify_messages(new_messages, hf_client, model=model)
        logger.info(f"Filtered to {len(filtered)} song titles")

        # Deduplicate and append
        added = 0
        for msg in filtered:
            if msg["id"] not in known_ids:
                existing.append(msg)
                known_ids.add(msg["id"])
                added += 1
        logger.info(f"Added {added} new titles (total: {len(existing)})")
    else:
        logger.info("No new messages to process")

    # Save updated titles
    titles_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n")

    # Generate HTML
    html = generate_html(existing)
    html_output_path.write_text(html)
    logger.info(f"Generated HTML at {html_output_path} with {len(existing)} titles")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Song Titles Bot")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Skip Slack, just regenerate HTML")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    config = load_config(script_dir / args.config)

    hf_token = os.environ.get("HF_TOKEN", "")
    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")

    if not slack_token and not args.dry_run:
        logger.error("SLACK_BOT_TOKEN required")
        return 1
    if not hf_token and not args.dry_run:
        logger.error("HF_TOKEN required")
        return 1

    titles_path = script_dir / config["titles_path"]
    html_output_path = script_dir / config["html_output_path"]

    if args.dry_run:
        # Just regenerate HTML from existing titles
        existing = json.loads(titles_path.read_text()) if titles_path.exists() else []
        html = generate_html(existing)
        html_output_path.write_text(html)
        logger.info(f"Dry run: regenerated HTML with {len(existing)} titles")
        return 0

    return run_bot(
        titles_path=titles_path,
        html_output_path=html_output_path,
        channel_name=config["channel"],
        hf_token=hf_token,
        slack_token=slack_token,
        model=config["model"],
    )


if __name__ == "__main__":
    sys.exit(main())

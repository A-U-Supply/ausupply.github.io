#!/usr/bin/env python3
"""Surreal Prompt Bot - Daily surrealist drawing prompts from news headlines."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate surreal drawing prompts from news")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't post to Slack")
    parser.add_argument("--channel", help="Override Slack channel")
    parser.add_argument("--temperature", type=float, help="LLM temperature (0.0-2.0)")
    parser.add_argument("--sources", help="Comma-separated list of news sources")
    parser.add_argument("--no-inspirations", action="store_true", help="Skip inspiration file")
    parser.add_argument("--config", default="config.yaml", help="Config file path")

    args = parser.parse_args()

    print("Surreal Prompt Bot - Not yet implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())

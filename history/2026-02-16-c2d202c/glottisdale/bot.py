"""GitHub Actions entrypoint for glottisdale.

Adds the slack/ subdirectory to sys.path so glottisdale_slack is importable,
then delegates to the CLI.
"""

import sys
from pathlib import Path

# Add slack package to path
slack_dir = Path(__file__).parent / "slack"
sys.path.insert(0, str(slack_dir))

from glottisdale.cli import main

if __name__ == "__main__":
    main()

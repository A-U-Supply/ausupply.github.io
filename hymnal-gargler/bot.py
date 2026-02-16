"""GitHub Actions entrypoint for Hymnal Gargler.

Adds the hymnal-gargler directory to sys.path so sibling modules are importable,
then delegates to the CLI.
"""

import sys
from pathlib import Path

# Add hymnal-gargler package to path so sibling imports work
pkg_dir = Path(__file__).parent
sys.path.insert(0, str(pkg_dir))

# Also add glottisdale slack module to path (needed by slack_fetcher)
glottisdale_slack_dir = pkg_dir.parent / "glottisdale" / "slack"
sys.path.insert(0, str(glottisdale_slack_dir))

from cli import main

if __name__ == "__main__":
    main()

"""Real browser check for visible suggestions, listening flags and source navigation."""

import sys

from run_grouping_browser import main

if __name__ == "__main__":
    sys.exit(
        main(
            server_script="tests/proofreading_browser_server.py",
            browser_script="tests/browser-suggestion-discovery.cjs",
            restart_script=None,
            default_port="8771",
            prefix="local-scribe-discovery-",
        )
    )

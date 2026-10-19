"""Run isolated Chromium/HTTP proofreading checks and restart with a synthetic model."""

import sys

from run_grouping_browser import main

if __name__ == "__main__":
    sys.exit(
        main(
            server_script="tests/proofreading_browser_server.py",
            browser_script="tests/browser-proofreading.cjs",
            restart_script="tests/browser-proofreading-restart.cjs",
            default_port="8771",
            prefix="local-scribe-proofreading-",
        )
    )

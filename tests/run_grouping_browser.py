"""Run real HTTP + Chromium, restart HTTP process, then verify persisted Undo/Redo.

Uses a new synthetic store under TMPDIR unless an explicit test root is supplied.
No ASR/diarization worker or model is started.
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def run_phase(script, env):
    server = subprocess.Popen([sys.executable, "tests/grouping_browser_server.py"], env=env)
    try:
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError("Fixture server exited before readiness.")
            try:
                with urllib.request.urlopen(env["GROUPING_BASE"] + "/api/session", timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Fixture server did not become ready.")
        return subprocess.run(["node", script], env=env, check=False).returncode
    finally:
        server.terminate()
        server.wait(timeout=10)


def main():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    if "LOCALSCRIBE_GROUPING_TEST_ROOT" not in env:
        env["LOCALSCRIBE_GROUPING_TEST_ROOT"] = tempfile.mkdtemp(prefix="local-scribe-grouping-", dir=os.environ["TMPDIR"])
    print(f"Synthetic test artifacts: {Path(env['LOCALSCRIBE_GROUPING_TEST_ROOT']).resolve()}", flush=True)
    port = env.get("LOCALSCRIBE_GROUPING_TEST_PORT", "8770")
    env["GROUPING_BASE"] = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(env["GROUPING_BASE"] + "/api/session", timeout=1):
            raise RuntimeError("Fixture port is occupied; select another LOCALSCRIBE_GROUPING_TEST_PORT.")
    except (OSError, urllib.error.URLError):
        pass
    result = run_phase("tests/browser-grouping.cjs", env)
    if result or env.get("UI_CONTRACT_FIXTURE") == "1":
        return result
    return run_phase("tests/browser-grouping-restart.cjs", env)


if __name__ == "__main__":
    sys.exit(main())

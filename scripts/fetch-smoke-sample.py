"""Fetch the public Whisper JFK smoke input; never a release quality reference."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
# Fixed public upstream fixture; no user-supplied destination URL or request body.
url = "https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac"
args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
with urllib.request.urlopen(url, timeout=60) as response:
    data = response.read(4 * 1024 * 1024)
if not data.startswith(b"fLaC"):
    raise SystemExit("Upstream fixture is not FLAC.")
args.output.write_bytes(data)
args.output.chmod(0o600)
print(f"Downloaded public smoke fixture: {len(data)} bytes; sha256={hashlib.sha256(data).hexdigest()}")

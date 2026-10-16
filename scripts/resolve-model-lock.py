"""Maintainer-only explicit revision resolution; never invoked during startup."""
import argparse
import json
import os
from pathlib import Path

from localscribe.models import REPOSITORIES

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
os.environ["HF_HUB_OFFLINE"] = "0"
from huggingface_hub import HfApi, constants
constants.HF_HUB_OFFLINE = False
api = HfApi()
resolved = {name: {"repo": repo, "revision": api.model_info(repo).sha}
            for name, repo in REPOSITORIES.items()}
args.output.write_text(json.dumps(resolved, indent=2) + "\n")
print(json.dumps(resolved))

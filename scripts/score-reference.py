#!/usr/bin/env python3
"""Score private corrected references against exported JSON; output aggregate counts only."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from localscribe.scoring import score_reference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--text-source", choices=("raw", "saved"), default="raw")
    parser.add_argument(
        "--speaker-source", choices=("segments", "exclusive", "regular"), default="segments"
    )
    parser.add_argument(
        "--collar",
        type=float,
        default=0.25,
        help="Excluded seconds on each side of every reference boundary",
    )
    args = parser.parse_args()
    try:
        result = score_reference(
            json.loads(args.reference.read_text()),
            json.loads(args.transcript.read_text()),
            text_source=args.text_source,
            speaker_source=args.speaker_source,
            collar=args.collar,
        )
        content = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(content)
        else:
            print(content, end="")
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(
            1,
            "Scoring failed. Check readable JSON files, required text/turn fields, and finite timestamps.\n",
        )


if __name__ == "__main__":
    main()

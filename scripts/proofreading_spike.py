"""Explicit real-model check on synthetic PL/EN/mixed passages; private output only.

This checks compatibility and produces material for manual quality review. It never
claims accuracy from a schema pass, starts a model, or downloads model assets.
"""

import argparse
import json
import time
from pathlib import Path

from localscribe.heavy import heavy_slot, uncertain_model
from localscribe.proofreading import LocalModel, chunks, validate_response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = args.output_root.expanduser().resolve()
    if output.is_relative_to(repository):
        parser.error("Use a private output directory outside the checkout.")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    passages = json.loads((repository / "tests/fixtures/proofreading-acceptance.json").read_text())
    segments = [
        {"id": f"p{i}", "text": text, "editedText": None} for i, text in enumerate(passages)
    ]
    glossary = ["Marcin", "Anna", "LocalScribe", "Snowflake", "Kowalski", "Vikram"]
    model = LocalModel()
    provenance = model.readiness()
    reports = []
    started = time.monotonic()
    with heavy_slot() as descriptor:
        if not descriptor:
            parser.exit(
                1, "Another heavy task or an unresolved model interruption blocks this check.\n"
            )
        for targets, context in chunks(segments, {s["id"] for s in segments}, glossary):
            with uncertain_model(model):
                raw = model.generate(targets, context, glossary)
            changes = validate_response(raw, targets, glossary)
            reports.append(
                {
                    "targets": targets,
                    "raw": raw,
                    "validated": changes,
                    "metrics": model.last_metrics,
                }
            )
    report = {
        "provenance": provenance,
        "passages": len(passages),
        "seconds": time.monotonic() - started,
        "suggestions": sum(len(r["validated"]) for r in reports),
        "batches": reports,
        "manualQualityReviewRequired": True,
    }
    path = output / "proofreading-spike.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    path.chmod(0o600)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("passages", "seconds", "suggestions", "manualQualityReviewRequired")
            }
        )
    )


if __name__ == "__main__":
    main()

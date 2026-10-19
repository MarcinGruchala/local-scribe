"""Real HTTP browser fixture; deterministic local adapter, never loads a model."""

import time

import uvicorn
from grouping_browser_server import fixture_app
from localscribe.worker import Worker


def main():
    app, root, port = fixture_app()

    class SyntheticModel:
        def readiness(self):
            return {"ready": True, "model": "synthetic-browser", "prompt": "test"}

        def generate(self, targets, context, glossary):
            mode = (root / "mode.txt").read_text() if (root / "mode.txt").exists() else "normal"
            time.sleep(0.15)
            if mode == "malformed":
                return {"changes": [{"id": "unknown", "old": "x", "new": "x", "uncertain": False}]}
            if mode == "mixed":
                return {
                    "changes": [
                        {
                            "id": s["id"],
                            "old": s["text"],
                            "new": s["text"] if i else s["text"].rstrip(".!") + "!",
                            "uncertain": bool(i),
                        }
                        for i, s in enumerate(targets)
                    ]
                }
            return {
                "changes": [
                    {
                        "id": s["id"],
                        "old": s["text"],
                        "new": s["text"].rstrip(".!") + "!",
                        "uncertain": False,
                    }
                    for s in targets
                ]
            }

    from localscribe import heavy

    heavy.LOCK = root / "synthetic-heavy.lock"
    heavy.MARKER = root / "synthetic-heavy.json"
    service = app.state.proofreading
    service.model = SyntheticModel()
    worker = Worker(app.state.jobs, root / "no-models", proofreading=service)
    app.state.worker = worker
    worker.start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, access_log=False)
    finally:
        worker.stop()


if __name__ == "__main__":
    main()

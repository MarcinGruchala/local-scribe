"""Single-store launcher bound exclusively to IPv4 loopback."""

import argparse
import fcntl
import os
import threading
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .config import Settings


class AlreadyRunningError(RuntimeError):
    """Another launcher already owns this data store."""


@contextmanager
def instance_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "launcher.lock").open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunningError(
                "LocalScribe is already running for this data directory."
            ) from exc
        try:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local LocalScribe application.")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--model-root", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env(
        data_root=args.data_root, model_root=args.model_root, port=args.port
    )
    import uvicorn

    from .api import create_app

    try:
        with instance_lock(settings.data_root):
            repository = Path(__file__).resolve().parents[3]
            if settings.data_root == repository / "output":
                from .migration import migrate_legacy_store

                migrate_legacy_store(settings.data_root, settings.model_root)
            app = create_app(settings)
            from .worker import Worker

            worker = Worker(app.state.jobs, settings.model_root, proofreading=app.state.proofreading)
            app.state.worker = worker
            worker.start()
            browser_timer = None
            if not args.no_browser:
                browser_timer = threading.Timer(
                    0.75, webbrowser.open, args=(f"http://127.0.0.1:{settings.port}",)
                )
                browser_timer.daemon = True
                browser_timer.start()
            try:
                uvicorn.run(app, host="127.0.0.1", port=settings.port, access_log=False)
            finally:
                if browser_timer:
                    browser_timer.cancel()
                worker.stop()
    except (AlreadyRunningError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

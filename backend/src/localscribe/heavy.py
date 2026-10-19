"""Cross-store process lock and fail-closed barrier for uncertain model completion."""

import fcntl
import http.client
import json
import os
from contextlib import contextmanager
from pathlib import Path

# Shared by this user's stores; no private transcript content is written here.
ROOT = Path("/private/tmp" if Path("/private/tmp").is_dir() else "/tmp")
LOCK = ROOT / f"localscribe-heavy-{os.getuid()}.lock"
MARKER = ROOT / f"localscribe-heavy-{os.getuid()}.json"


def blocked():
    if not MARKER.exists():
        return False
    try:
        from .proofreading import LocalModel

        adapter = LocalModel()
        marker = json.loads(MARKER.read_text())
        if marker["endpoint"] != adapter.endpoint:
            return True
        models = adapter.request("GET", "/api/v1/models")["models"]
        # Only an observed unload proves an interrupted request cannot still generate.
        if any(i["id"] == marker["model"] for m in models for i in m.get("loaded_instances", [])):
            return True
        MARKER.unlink(missing_ok=True)
        return False
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
        return True


@contextmanager
def heavy_slot():
    descriptor = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield not blocked()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def uncertain_model(adapter):
    """Cancellation drains a request; transport failure/crash retains the barrier."""
    if not hasattr(adapter, "endpoint"):
        yield  # Deterministic adapters have no independently running model server.
        return
    descriptor = os.open(MARKER, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump({"endpoint": adapter.endpoint, "model": adapter.model}, handle)
        handle.flush()
        os.fsync(handle.fileno())
    yield
    MARKER.unlink(missing_ok=True)

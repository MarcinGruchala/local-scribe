"""Local model completeness and integrity, without downloads or credentials."""

import hashlib
import json

import pytest
from localscribe.models import inspect, local_path, readiness


def snapshot(tmp_path):
    folder = tmp_path / "fast"
    folder.mkdir()
    files = {"config.json": b"{}", "weights.npz": b"not-real-weights"}
    for name, content in files.items():
        (folder / name).write_bytes(content)
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "repo": "mlx-community/whisper-large-v3-turbo",
                "revision": "a" * 40,
                "files": {
                    name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                    for name, content in files.items()
                },
            }
        )
    )
    return folder


def test_missing_models_never_download(tmp_path):
    assert not any(item["ready"] for item in readiness(tmp_path).values())
    with pytest.raises(RuntimeError, match="missing or corrupt"):
        local_path(tmp_path, "fast")


def test_hash_check_rejects_same_size_corruption(tmp_path):
    folder = snapshot(tmp_path)
    assert inspect(tmp_path, "fast", hashes=True)["ready"]
    (folder / "config.json").write_bytes(b"[]")
    assert not inspect(tmp_path, "fast", hashes=True)["ready"]


def test_manifest_cannot_escape_model_directory(tmp_path):
    folder = snapshot(tmp_path)
    path = folder / "manifest.json"
    value = json.loads(path.read_text())
    value["files"]["../../secret"] = {"bytes": 1, "sha256": "fake"}
    path.write_text(json.dumps(value))
    assert not inspect(tmp_path, "fast")["ready"]

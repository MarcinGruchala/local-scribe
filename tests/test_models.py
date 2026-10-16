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


def test_readiness_rehashes_when_same_size_asset_changes(tmp_path):
    folder = snapshot(tmp_path)
    assert readiness(tmp_path)["fast"]["ready"]
    (folder / "config.json").write_bytes(b"[]")
    assert not readiness(tmp_path)["fast"]["ready"]


def test_doctor_never_exposes_credentials_or_private_paths(tmp_path, monkeypatch):
    from localscribe.models import doctor

    monkeypatch.setenv("HF_TOKEN", "sensitive-download-token")
    monkeypatch.setenv("LOCALSCRIBE_DATA_ROOT", str(tmp_path / "private-store"))
    report = json.dumps(doctor(tmp_path / "absent-models"))
    assert "sensitive-download-token" not in report
    assert str(tmp_path) not in report
    assert "availableBytes" in report


def test_quality_requires_matching_native_compatibility_evidence(tmp_path):
    folder = snapshot(tmp_path)
    target = tmp_path / "quality"
    folder.rename(target)
    path = target / "manifest.json"
    value = json.loads(path.read_text())
    value["repo"] = "mlx-community/whisper-large-v3-mlx"
    path.write_text(json.dumps(value))
    assert inspect(tmp_path, "quality", hashes=True)["ready"]
    assert not readiness(tmp_path)["quality"]["ready"]
    evidence = target / "compatibility.json"
    evidence.write_text(json.dumps({"revision": "a" * 40, "passed": True}))
    assert readiness(tmp_path)["quality"]["ready"]
    evidence.write_text(json.dumps({"revision": "b" * 40, "passed": True}))
    assert not readiness(tmp_path)["quality"]["ready"]


def test_doctor_requires_speakers_unless_asr_only_is_explicit(monkeypatch, capsys):
    import sys

    from localscribe import models

    monkeypatch.setattr(
        models,
        "doctor",
        lambda _: {
            "ffmpeg": True,
            "ffprobe": True,
            "models": {"fast": {"ready": True}, "diarization": {"ready": False}},
            "storage": {"writable": True, "availableBytes": 1024**3},
            "architecture": "arm64",
            "packages": {"mlx": "test"},
        },
    )
    monkeypatch.setattr(sys, "argv", ["localscribe-models", "doctor"])
    with pytest.raises(SystemExit) as error:
        models.main()
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)["ready"] is False
    monkeypatch.setattr(sys, "argv", ["localscribe-models", "doctor", "--asr-only"])
    models.main()
    assert json.loads(capsys.readouterr().out)["ready"] is True

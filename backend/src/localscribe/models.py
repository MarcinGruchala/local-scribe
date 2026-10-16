"""Explicit model provisioning and local-only integrity checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

REPOSITORIES = {
    "fast": "mlx-community/whisper-large-v3-turbo",
    "quality": "mlx-community/whisper-large-v3-mlx",
    "diarization": "pyannote/speaker-diarization-community-1",
}
LOCK = Path(__file__).resolve().parents[3] / "model-lock.json"
_integrity_cache: dict[tuple[str, str], tuple[tuple, dict]] = {}


def default_root() -> Path:
    return Path(
        os.environ.get("LOCALSCRIBE_MODEL_ROOT", Path.home() / "Library/Caches/LocalScribe/models")
    )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inspect(root: Path, profile: str, *, hashes: bool = False) -> dict:
    folder = root / profile
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest["repo"] != REPOSITORIES[profile] or len(manifest["revision"]) != 40:
            raise ValueError("Invalid revision manifest")
        files = manifest["files"]
        required = {"config.yaml"} if profile == "diarization" else {"config.json"}
        if not required.issubset(files) or not any(
            k.endswith((".npz", ".safetensors", ".bin")) for k in files
        ):
            raise ValueError("Incomplete model snapshot")
        for name, entry in files.items():
            path = folder / name
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError("Unsafe model path")
            if not path.is_file() or path.stat().st_size != entry["bytes"]:
                raise ValueError("Missing or incomplete asset")
            if hashes and digest(path) != entry["sha256"]:
                raise ValueError("Corrupt model asset")
        return {"ready": True, "repo": manifest["repo"], "revision": manifest["revision"]}
    except (OSError, ValueError, KeyError, TypeError):
        return {
            "ready": False,
            "repo": REPOSITORIES[profile],
            "message": f"Run make models PROFILE={profile}, then make doctor.",
        }


def local_path(root: Path, profile: str) -> Path:
    if not inspect(root, profile, hashes=True)["ready"]:
        raise RuntimeError(
            "Model assets are missing or corrupt. Run explicit model setup and doctor."
        )
    return (root / profile).resolve()


def readiness(root: Path) -> dict:
    result = {}
    for name in REPOSITORIES:
        folder = root / name
        try:
            manifest_path = folder / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            paths = [manifest_path, *(folder / item for item in manifest["files"])]
            fingerprint = tuple(
                (str(path), path.stat().st_size, path.stat().st_mtime_ns) for path in paths
            )
            key = (str(root.resolve()), name)
            cached = _integrity_cache.get(key)
            if cached is None or cached[0] != fingerprint:
                _integrity_cache[key] = (fingerprint, inspect(root, name, hashes=True))
            result[name] = dict(_integrity_cache[key][1])
        except (OSError, ValueError, KeyError, TypeError):
            result[name] = inspect(root, name)
    return result


def provision(root: Path, profile: str, *, resolve: bool = False) -> dict:
    # Network access is confined to this explicitly invoked setup operation.
    os.environ["HF_HUB_OFFLINE"] = "0"
    from huggingface_hub import HfApi, constants, snapshot_download

    constants.HF_HUB_OFFLINE = False
    lock = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    repo = REPOSITORIES[profile]
    revision = (
        HfApi().model_info(repo).sha
        if resolve or profile not in lock
        else lock[profile]["revision"]
    )
    folder = root / profile
    folder.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo, revision=revision, local_dir=folder)
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file() and ".cache" not in path.parts and path.name != "manifest.json":
            files[str(path.relative_to(folder))] = {
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
    manifest = {"repo": repo, "revision": revision, "files": files}
    temporary = folder / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(folder / "manifest.json")
    lock[profile] = {"repo": repo, "revision": revision}
    if resolve or not LOCK.exists():
        LOCK.write_text(json.dumps(lock, indent=2) + "\n")
    return {"profile": profile, "revision": revision, "fileCount": len(files)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["download", "doctor"])
    parser.add_argument("--profile", choices=REPOSITORIES, default="fast")
    parser.add_argument("--root", type=Path, default=default_root())
    parser.add_argument(
        "--resolve", action="store_true", help="Explicitly update the repository revision lock"
    )
    args = parser.parse_args()
    if args.action == "download":
        try:
            print(json.dumps(provision(args.root, args.profile, resolve=args.resolve)))
        except Exception:  # noqa: BLE001 - redact third-party errors at the process boundary
            # Third-party exceptions may include credential-bearing request details.
            print(
                "Model download failed. Check network, disk space, and gated access in your Hugging Face account. Do not paste tokens.",
                file=sys.stderr,
            )
            raise SystemExit(1)
    else:
        result = {
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "ffprobe": bool(shutil.which("ffprobe")),
            "models": {k: inspect(args.root, k, hashes=True) for k in REPOSITORIES},
        }
        print(json.dumps(result, indent=2))
        if not result["ffmpeg"] or not result["ffprobe"] or not result["models"]["fast"]["ready"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

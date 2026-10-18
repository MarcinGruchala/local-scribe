"""Explicit local paths and loopback server settings."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path
    model_root: Path
    frontend_dist: Path
    port: int = 8765

    @classmethod
    def from_env(
        cls,
        *,
        data_root: Path | None = None,
        model_root: Path | None = None,
        port: int | None = None,
    ) -> "Settings":
        repository = Path(__file__).resolve().parents[3]
        default_root = repository / "output"
        settings = cls(
            data_root=Path(data_root or os.environ.get("LOCALSCRIBE_DATA_ROOT", default_root))
            .expanduser()
            .resolve(),
            model_root=Path(
                model_root
                or os.environ.get(
                    "LOCALSCRIBE_MODEL_ROOT",
                    Path.home() / "Library" / "Caches" / "LocalScribe" / "models",
                )
            )
            .expanduser()
            .resolve(),
            frontend_dist=Path(
                os.environ.get("LOCALSCRIBE_FRONTEND_DIST", repository / "frontend" / "dist")
            )
            .expanduser()
            .resolve(),
            port=port if port is not None else int(os.environ.get("LOCALSCRIBE_PORT", "8765")),
        )
        if not 1 <= settings.port <= 65535:
            raise ValueError("Port must be between 1 and 65535.")
        if settings.model_root.is_relative_to(repository):
            raise ValueError("Model directories must be outside the repository.")
        if settings.data_root.is_relative_to(repository) and not settings.data_root.is_relative_to(
            repository / "output"
        ):
            raise ValueError("Private data must use ignored output/ or stay outside the repository.")
        return settings

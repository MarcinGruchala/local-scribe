"""Local SQLite connections and application-owned file roots."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Storage:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.database = self.root / "localscribe.sqlite3"
        self.jobs_root = self.root / "jobs"
        self.imports_root = self.root / "imports"

    def initialize(self) -> None:
        for directory in (self.root, self.jobs_root, self.imports_root):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)")
        self.database.chmod(0o600)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

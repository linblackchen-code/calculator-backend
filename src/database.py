"""SQLite persistence; every operation uses its own connection."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS calculation_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "expression TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL, "
                "is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)))"
            )
            # Upgrade an existing assignment database without replacing its history.
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(calculation_history)")}
            if "is_favorite" not in columns:
                connection.execute(
                    "ALTER TABLE calculation_history ADD COLUMN "
                    "is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1))"
                )

    def insert(self, expression: str, result: str) -> dict:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO calculation_history (expression, result, created_at) VALUES (?, ?, ?)",
                (expression, result, created_at),
            )
            return {"id": cursor.lastrowid, "expression": expression, "result": result, "created_at": created_at, "is_favorite": False}

    @staticmethod
    def filters(search: str, favorites_only: bool) -> tuple[str, tuple]:
        # Parameter binding prevents SQL injection; escape LIKE wildcard characters.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        condition = "WHERE (expression LIKE ? ESCAPE '\\' OR result LIKE ? ESCAPE '\\')"
        if favorites_only:
            condition += " AND is_favorite = 1"
        return condition, (pattern, pattern)

    @staticmethod
    def record(row: sqlite3.Row) -> dict:
        return {**dict(row), "is_favorite": bool(row["is_favorite"])}

    def list(self, page: int, limit: int, search: str, favorites_only: bool = False) -> dict:
        condition, parameters = self.filters(search, favorites_only)
        with self.connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM calculation_history {condition}", parameters
            ).fetchone()[0]
            records = connection.execute(
                f"SELECT * FROM calculation_history {condition} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*parameters, limit, (page - 1) * limit),
            ).fetchall()
        return {"items": [self.record(row) for row in records], "total": total, "page": page, "limit": limit}

    def export(self, search: str, favorites_only: bool) -> list[dict]:
        condition, parameters = self.filters(search, favorites_only)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM calculation_history {condition} ORDER BY id DESC", parameters
            ).fetchall()
        return [self.record(row) for row in rows]

    def set_favorite(self, record_id: int, is_favorite: bool) -> dict | None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE calculation_history SET is_favorite = ? WHERE id = ?", (int(is_favorite), record_id)
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute("SELECT * FROM calculation_history WHERE id = ?", (record_id,)).fetchone()
            return self.record(row)

    def delete(self, record_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM calculation_history WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

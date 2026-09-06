"""SQLite-backed webhook delivery store."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class EventStore:
    def __init__(self, database_url: str):
        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Only sqlite databases are supported")
        self.path = Path(database_url.removeprefix(prefix))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS webhook_events (
                delivery_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
                action TEXT, payload TEXT NOT NULL, received_at TEXT NOT NULL)"""
            )

    def add(
        self, delivery_id: str, event_type: str, action: str | None, payload: dict[str, Any]
    ) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO webhook_events VALUES (?, ?, ?, ?, ?)",
                    (
                        delivery_id,
                        event_type,
                        action,
                        json.dumps(payload),
                        datetime.now(UTC).isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT delivery_id, event_type, action, payload, received_at "
                "FROM webhook_events ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

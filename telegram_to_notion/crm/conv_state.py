"""SQLite-backed per-chat conversation state for Telegram CRM commands."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field


@dataclass
class ConvState:
    chat_id: int
    command: str
    collected: dict[str, str] = field(default_factory=dict)
    pending_field: str | None = None
    created_at: float = field(default_factory=time.time)


class ConvStateStore:
    TIMEOUT_SECONDS = 1800  # 30 minutes

    def __init__(self, db_path: str = "data/conv_state.db") -> None:
        self._db_path = db_path
        self._init_db()
        self.clear_stale()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conv_state (
                    chat_id   INTEGER PRIMARY KEY,
                    command   TEXT    NOT NULL,
                    collected TEXT    NOT NULL DEFAULT '{}',
                    pending_field TEXT,
                    created_at REAL   NOT NULL
                )
            """)
            conn.commit()

    def get(self, chat_id: int) -> ConvState | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT command, collected, pending_field, created_at FROM conv_state WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if row is None:
            return None
        command, collected_json, pending_field, created_at = row
        if time.time() - created_at > self.TIMEOUT_SECONDS:
            self.clear(chat_id)
            return None
        return ConvState(
            chat_id=chat_id,
            command=command,
            collected=json.loads(collected_json),
            pending_field=pending_field,
            created_at=created_at,
        )

    def set(self, state: ConvState) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO conv_state
                   (chat_id, command, collected, pending_field, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    state.chat_id,
                    state.command,
                    json.dumps(state.collected),
                    state.pending_field,
                    state.created_at,
                ),
            )
            conn.commit()

    def clear(self, chat_id: int) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM conv_state WHERE chat_id = ?", (chat_id,))
            conn.commit()

    def clear_stale(self) -> None:
        cutoff = time.time() - self.TIMEOUT_SECONDS
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM conv_state WHERE created_at < ?", (cutoff,))
            conn.commit()

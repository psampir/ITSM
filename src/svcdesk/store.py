# ai-generated: 80% - opencode drafted the SQLite persistence layer; reviewed by the student
"""SQLite-backed ticket store. One row per ticket, persisted so tickets survive a restart."""

from __future__ import annotations

import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        directory = os.path.dirname(DB_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        _conn.commit()
    return _conn


def save(ticket: dict) -> None:
    with _lock:
        conn = _connection()
        conn.execute(
            "INSERT OR REPLACE INTO tickets (id, data) VALUES (?, ?)",
            (ticket["id"], json.dumps(ticket)),
        )
        conn.commit()


def get(ticket_id: str) -> dict | None:
    with _lock:
        row = _connection().execute("SELECT data FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return json.loads(row[0]) if row else None


def all_tickets() -> list[dict]:
    with _lock:
        rows = _connection().execute("SELECT data FROM tickets").fetchall()
    return [json.loads(row[0]) for row in rows]

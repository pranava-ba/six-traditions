"""
db.py — SQLite access layer for temples.db
"""

import sqlite3, pathlib, contextlib
from typing import Iterator

DB_PATH = pathlib.Path(__file__).parent.parent / "temples.db"


@contextlib.contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def all_temples() -> list[dict]:
    with get_conn() as con:
        rows = con.execute("SELECT * FROM temples ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def flagged_temples() -> list[dict]:
    with get_conn() as con:
        rows = con.execute("SELECT * FROM flagged ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_session(session_id: str) -> dict:
    import json
    with get_conn() as con:
        row = con.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return json.loads(row["state_json"]) if row else {}


def save_session(session_id: str, state: dict) -> None:
    import json
    with get_conn() as con:
        con.execute(
            """INSERT INTO sessions(session_id, state_json, updated_at)
               VALUES(?, ?, datetime('now'))
               ON CONFLICT(session_id) DO UPDATE
               SET state_json = excluded.state_json,
                   updated_at = excluded.updated_at""",
            (session_id, json.dumps(state, ensure_ascii=False)),
        )
        con.commit()


def clear_session(session_id: str) -> None:
    with get_conn() as con:
        con.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        con.commit()

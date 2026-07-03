"""SQLite-backed cache, pending Telegram confirmations, and the private expense log."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache   (key TEXT PRIMARY KEY, payload TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, payload TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS expenses(id TEXT PRIMARY KEY, amount_dkk REAL, title TEXT,
                                    noted_at TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS review_queue(
    id TEXT PRIMARY KEY,
    source_text TEXT,
    chat_id INTEGER,
    pass1_parsed TEXT,
    received_at TEXT,
    created_ref TEXT,
    created_at REAL,
    status TEXT DEFAULT 'pending'
);
"""


@contextmanager
def _db():
    con = sqlite3.connect(config.DB_PATH)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with _db() as con:
        con.executescript(_SCHEMA)


def set_cache(key: str, payload) -> None:
    with _db() as con:
        con.execute(
            "INSERT INTO cache(key,payload,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (key, json.dumps(payload, ensure_ascii=False), time.time()),
        )


def get_cache(key: str, max_age: float | None = None):
    with _db() as con:
        row = con.execute("SELECT payload, updated_at FROM cache WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    if max_age is not None and time.time() - row[1] > max_age:
        return None
    return json.loads(row[0])


def add_pending(payload: dict) -> str:
    pid = uuid.uuid4().hex[:12]
    with _db() as con:
        con.execute(
            "INSERT INTO pending(id,payload,created_at) VALUES(?,?,?)",
            (pid, json.dumps(payload, ensure_ascii=False), time.time()),
        )
    return pid


def pop_pending(pid: str) -> dict | None:
    with _db() as con:
        row = con.execute("SELECT payload FROM pending WHERE id=?", (pid,)).fetchone()
        con.execute("DELETE FROM pending WHERE id=?", (pid,))
    return json.loads(row[0]) if row else None


def log_expense(title: str, amount_dkk: float, noted_at: str, raw: str) -> str:
    row_id = uuid.uuid4().hex
    with _db() as con:
        con.execute(
            "INSERT INTO expenses(id,amount_dkk,title,noted_at,raw) VALUES(?,?,?,?,?)",
            (row_id, amount_dkk, title, noted_at, raw),
        )
    return row_id


def get_expense(row_id: str) -> dict | None:
    with _db() as con:
        row = con.execute(
            "SELECT title, amount_dkk, noted_at, raw FROM expenses WHERE id=?", (row_id,)
        ).fetchone()
    if not row:
        return None
    return {"title": row[0], "amount_dkk": row[1], "noted_at": row[2], "raw": row[3]}


def update_expense(row_id: str, title: str, amount_dkk: float) -> None:
    with _db() as con:
        con.execute("UPDATE expenses SET title=?, amount_dkk=? WHERE id=?",
                    (title, amount_dkk, row_id))


def delete_expense(row_id: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM expenses WHERE id=?", (row_id,))


def recent_expenses(limit: int = 10) -> list[dict]:
    with _db() as con:
        rows = con.execute(
            "SELECT title, amount_dkk, noted_at FROM expenses ORDER BY noted_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"title": r[0], "amount_dkk": r[1], "noted_at": r[2]} for r in rows]


# ── Review queue (dual-pass quality pass) ──────────────────────────
# Pass 1 executes immediately; each result is queued here so the strong
# model can re-check it later. `received_at` is the message's ORIGINAL
# arrival time (the "NU" anchor for re-parsing relative dates), and
# `created_ref` is a JSON list of references to whatever was created.


def enqueue_review(source_text: str, chat_id: int, pass1_parsed: dict,
                   received_at: str, created_ref: list[dict]) -> str:
    rid = uuid.uuid4().hex
    with _db() as con:
        con.execute(
            "INSERT INTO review_queue(id,source_text,chat_id,pass1_parsed,received_at,"
            "created_ref,created_at,status) VALUES(?,?,?,?,?,?,?,'pending')",
            (rid, source_text, chat_id, json.dumps(pass1_parsed, ensure_ascii=False),
             received_at, json.dumps(created_ref, ensure_ascii=False), time.time()),
        )
    return rid


def list_pending_reviews(limit: int = 10) -> list[dict]:
    with _db() as con:
        rows = con.execute(
            "SELECT id, source_text, chat_id, pass1_parsed, received_at, created_ref, "
            "created_at FROM review_queue WHERE status='pending' ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()
    return [{
        "id": r[0], "source_text": r[1], "chat_id": r[2],
        "pass1_parsed": json.loads(r[3]), "received_at": r[4],
        "created_ref": json.loads(r[5]), "created_at": r[6],
    } for r in rows]


def mark_review(rid: str, status: str) -> None:
    with _db() as con:
        con.execute("UPDATE review_queue SET status=? WHERE id=?", (status, rid))


def update_review_ref(rid: str, created_ref: list[dict]) -> None:
    # Written BEFORE the old action is deleted on an intent-type switch, so a
    # crash mid-correction cannot duplicate actions on re-run.
    with _db() as con:
        con.execute("UPDATE review_queue SET created_ref=? WHERE id=?",
                    (json.dumps(created_ref, ensure_ascii=False), rid))

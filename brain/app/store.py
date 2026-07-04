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
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS aula_messages (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT, from_addr TEXT, subject TEXT,
    mail_date TEXT NOT NULL,
    sender_verified INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'received',
    received_at TEXT NOT NULL,
    stream TEXT NOT NULL DEFAULT 'aula'
);
CREATE TABLE IF NOT EXISTS aula_items (
    id INTEGER PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES aula_messages(message_id),
    intent TEXT NOT NULL, title TEXT, summary TEXT,
    date TEXT, time TEXT, all_day INTEGER, deadline TEXT,
    confidence REAL, ambiguity_flags TEXT,
    status TEXT NOT NULL,
    gcal_event_id TEXT, vikunja_task_id INTEGER,
    created_at TEXT NOT NULL, resolved_at TEXT,
    stream TEXT NOT NULL DEFAULT 'aula',
    importance TEXT, sender_kind TEXT
);
"""

# Kolonner tilføjet efter Del 3 — ALTER'es ind på eksisterende databaser.
_MIGRATIONS = (
    "ALTER TABLE aula_messages ADD COLUMN stream TEXT NOT NULL DEFAULT 'aula'",
    "ALTER TABLE aula_items ADD COLUMN stream TEXT NOT NULL DEFAULT 'aula'",
    "ALTER TABLE aula_items ADD COLUMN importance TEXT",
    "ALTER TABLE aula_items ADD COLUMN sender_kind TEXT",
)


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
        for stmt in _MIGRATIONS:
            try:
                con.execute(stmt)
            except sqlite3.OperationalError:
                pass  # kolonnen findes allerede


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


# ── Key/value (gmail history cursor, aula edit-reply mapping) ──────


def kv_get(key: str) -> str | None:
    with _db() as con:
        row = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def kv_set(key: str, value: str) -> None:
    with _db() as con:
        con.execute(
            "INSERT INTO kv(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def kv_del(key: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM kv WHERE key=?", (key,))


# ── Aula-pipeline (Del 3) ───────────────────────────────────────────
# Messages are inserted with status=received BEFORE classification, so a
# crash mid-LLM leaves the row behind and the next poll resumes it.
# Bodies are never stored — they are re-fetched from Gmail by message_id.

_MSG_COLS = ("message_id", "thread_id", "from_addr", "subject", "mail_date",
             "sender_verified", "status", "received_at", "stream")

_ITEM_COLS = ("id", "message_id", "intent", "title", "summary", "date", "time",
              "all_day", "deadline", "confidence", "ambiguity_flags", "status",
              "gcal_event_id", "vikunja_task_id", "created_at", "resolved_at",
              "stream", "importance", "sender_kind")


def _msg_row(r) -> dict:
    return dict(zip(_MSG_COLS, r))


def _item_row(r) -> dict:
    d = dict(zip(_ITEM_COLS, r))
    d["ambiguity_flags"] = json.loads(d["ambiguity_flags"] or "[]")
    return d


def aula_insert_message(message_id: str, thread_id: str, from_addr: str,
                        subject: str, mail_date: str, sender_verified: bool,
                        received_at: str, stream: str = "aula",
                        status: str = "received") -> bool:
    """True if the row was new; False = already seen (idempotent)."""
    with _db() as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO aula_messages(message_id,thread_id,from_addr,"
            "subject,mail_date,sender_verified,status,received_at,stream) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (message_id, thread_id, from_addr, subject, mail_date,
             int(sender_verified), status, received_at, stream),
        )
        return cur.rowcount == 1


def aula_get_message(message_id: str) -> dict | None:
    with _db() as con:
        row = con.execute(
            f"SELECT {','.join(_MSG_COLS)} FROM aula_messages WHERE message_id=?",
            (message_id,),
        ).fetchone()
    return _msg_row(row) if row else None


def aula_set_message_status(message_id: str, status: str) -> None:
    with _db() as con:
        con.execute("UPDATE aula_messages SET status=? WHERE message_id=?",
                    (status, message_id))


def aula_received_messages(limit: int, stream: str = "aula") -> list[dict]:
    """Unclassified messages, oldest first (GMAIL_MAX_PER_POLL pr. tick)."""
    with _db() as con:
        rows = con.execute(
            f"SELECT {','.join(_MSG_COLS)} FROM aula_messages "
            "WHERE status='received' AND stream=? ORDER BY mail_date LIMIT ?",
            (stream, limit),
        ).fetchall()
    return [_msg_row(r) for r in rows]


def aula_items_for_message(message_id: str) -> list[dict]:
    with _db() as con:
        rows = con.execute(
            f"SELECT {','.join(_ITEM_COLS)} FROM aula_items WHERE message_id=?",
            (message_id,),
        ).fetchall()
    return [_item_row(r) for r in rows]


def aula_insert_item(message_id: str, *, intent: str, title: str, summary: str,
                     date: str | None, time: str | None, all_day: bool,
                     deadline: str | None, confidence: float,
                     ambiguity_flags: list[str], created_at: str,
                     stream: str = "aula", importance: str | None = None,
                     sender_kind: str | None = None) -> int:
    with _db() as con:
        cur = con.execute(
            "INSERT INTO aula_items(message_id,intent,title,summary,date,time,"
            "all_day,deadline,confidence,ambiguity_flags,status,created_at,"
            "stream,importance,sender_kind) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,'pending',?,?,?,?)",
            (message_id, intent, title, summary, date, time, int(all_day),
             deadline, confidence, json.dumps(ambiguity_flags), created_at,
             stream, importance, sender_kind),
        )
        return cur.lastrowid


def aula_get_item(item_id: int) -> dict | None:
    with _db() as con:
        row = con.execute(
            f"SELECT {','.join(_ITEM_COLS)} FROM aula_items WHERE id=?",
            (item_id,),
        ).fetchone()
    return _item_row(row) if row else None


def aula_update_item(item_id: int, *, status: str,
                     gcal_event_id: str | None = None,
                     vikunja_task_id: int | None = None,
                     resolved_at: str | None = None) -> None:
    with _db() as con:
        con.execute(
            "UPDATE aula_items SET status=?, "
            "gcal_event_id=COALESCE(?, gcal_event_id), "
            "vikunja_task_id=COALESCE(?, vikunja_task_id), "
            "resolved_at=COALESCE(?, resolved_at) WHERE id=?",
            (status, gcal_event_id, vikunja_task_id, resolved_at, item_id),
        )


def aula_expire_pending(cutoff_iso: str, resolved_at: str) -> int:
    """Proposals (event/handling) unanswered past the TTL. Info items are the
    brief queue and never expire this way."""
    with _db() as con:
        cur = con.execute(
            "UPDATE aula_items SET status='expired', resolved_at=? "
            "WHERE status='pending' AND intent IN ('event','handling') "
            "AND created_at < ?",
            (resolved_at, cutoff_iso),
        )
        return cur.rowcount


def aula_pending_info(stream: str = "aula") -> list[dict]:
    with _db() as con:
        rows = con.execute(
            f"SELECT {','.join(_ITEM_COLS)} FROM aula_items "
            "WHERE intent='info' AND status='pending' AND stream=? "
            "ORDER BY created_at",
            (stream,),
        ).fetchall()
    return [_item_row(r) for r in rows]


def aula_mark_briefed(item_ids: list[int], resolved_at: str) -> None:
    with _db() as con:
        con.executemany(
            "UPDATE aula_items SET status='briefed', resolved_at=? WHERE id=?",
            [(resolved_at, i) for i in item_ids],
        )


def aula_expired_since(since_iso: str, stream: str = "aula") -> int:
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM aula_items WHERE status='expired' "
            "AND resolved_at >= ? AND stream=?",
            (since_iso, stream),
        ).fetchone()
    return row[0]


def aula_feed(since_iso: str, today_iso: str, stream: str = "aula") -> dict:
    """Dashboard block: info items + recent proposals/autos with status."""
    with _db() as con:
        info = con.execute(
            "SELECT title, summary, created_at, status, importance, sender_kind "
            "FROM aula_items WHERE intent='info' AND created_at >= ? AND stream=? "
            "ORDER BY created_at DESC",
            (since_iso, stream),
        ).fetchall()
        recent = con.execute(
            "SELECT title, intent, status, date, time, created_at, deadline, "
            "importance, sender_kind FROM aula_items "
            "WHERE intent IN ('event','handling') AND created_at >= ? AND stream=? "
            "ORDER BY created_at DESC",
            (since_iso, stream),
        ).fetchall()
        new_today = con.execute(
            "SELECT COUNT(*) FROM aula_messages WHERE received_at >= ? "
            "AND stream=? AND status != 'skipped'",
            (today_iso, stream),
        ).fetchone()[0]
    return {
        "info": [{"title": r[0], "summary": r[1], "created_at": r[2],
                  "status": r[3], "importance": r[4], "sender_kind": r[5]}
                 for r in info],
        "recent": [{"title": r[0], "intent": r[1], "status": r[2], "date": r[3],
                    "time": r[4], "created_at": r[5], "deadline": r[6],
                    "importance": r[7], "sender_kind": r[8]} for r in recent],
        "new_today": new_today,
    }


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

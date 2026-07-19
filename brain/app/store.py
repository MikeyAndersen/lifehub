"""SQLite-backed cache, pending Telegram confirmations, and the private expense log."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config


def datetime_now_iso() -> str:
    return datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds")

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
CREATE TABLE IF NOT EXISTS sys_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT
);
CREATE INDEX IF NOT EXISTS idx_sys_events_ts ON sys_events(ts);
CREATE INDEX IF NOT EXISTS idx_sys_events_kind ON sys_events(kind, ts);
CREATE TABLE IF NOT EXISTS parse_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_text TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
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
    "ALTER TABLE aula_items ADD COLUMN deferred_until TEXT",
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
        # Ambient-stats (DEL 5): markér hvornår sys_events-loggen begyndte at
        # samle ind — tællere før dette tidspunkt findes ikke og opfindes aldrig.
        con.execute(
            "INSERT OR IGNORE INTO kv(key,value) VALUES('stats_since',?)",
            (datetime_now_iso(),),
        )


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


def get_cache_meta(key: str):
    """(payload, updated_at) eller None — så kalderen selv kan afgøre stale-alder."""
    with _db() as con:
        row = con.execute("SELECT payload, updated_at FROM cache WHERE key=?", (key,)).fetchone()
    if not row:
        return None
    return json.loads(row[0]), row[1]


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


def get_pending(pid: str) -> dict | None:
    """Læs uden at slette — bruges når en bekræftelse redigeres (fx intent-swap)
    før den til sidst oprettes eller droppes."""
    with _db() as con:
        row = con.execute("SELECT payload FROM pending WHERE id=?", (pid,)).fetchone()
    return json.loads(row[0]) if row else None


def update_pending(pid: str, payload: dict) -> None:
    with _db() as con:
        con.execute("UPDATE pending SET payload=? WHERE id=?",
                    (json.dumps(payload, ensure_ascii=False), pid))


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


# ── Ambient-stats: letvægts system-event-log (DEL 5) ───────────────
# Én række pr. hændelse (prompt, pass2-review, triage, vikunja-write …).
# Labels er bevidst generiske — /api/ambient er en delt flade, så der
# logges aldrig beskedtekst, mailemner eller andre private payloads.


def log_event(kind: str, label: str | None = None) -> None:
    """Fire-and-forget: statistik må ALDRIG vælte den handling der logges."""
    try:
        with _db() as con:
            con.execute("INSERT INTO sys_events(ts,kind,label) VALUES(?,?,?)",
                        (datetime_now_iso(), kind, label))
    except sqlite3.Error:
        pass


def count_events(kind: str | None = None, label: str | None = None,
                 since_iso: str | None = None) -> int:
    where, params = [], []
    if kind is not None:
        where.append("kind=?"); params.append(kind)
    if label is not None:
        where.append("label=?"); params.append(label)
    if since_iso is not None:
        where.append("ts>=?"); params.append(since_iso)
    sql = "SELECT COUNT(*) FROM sys_events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with _db() as con:
        return con.execute(sql, params).fetchone()[0]


def recent_events(limit: int = 30, after_id: int | None = None) -> list[dict]:
    """Nyeste events (id stigende). after_id → kun events nyere end den."""
    with _db() as con:
        if after_id is not None:
            rows = con.execute(
                "SELECT id, ts, kind, label FROM sys_events WHERE id>? "
                "ORDER BY id DESC LIMIT ?", (after_id, limit)).fetchall()
        else:
            rows = con.execute(
                "SELECT id, ts, kind, label FROM sys_events "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "ts": r[1], "kind": r[2], "label": r[3]}
            for r in reversed(rows)]


def event_hour_histogram(since_iso: str) -> list[tuple[str, int]]:
    """(time-streng "HH", antal) siden since_iso — til 'travleste time'."""
    with _db() as con:
        rows = con.execute(
            "SELECT substr(ts,12,2) AS h, COUNT(*) FROM sys_events "
            "WHERE ts>=? GROUP BY h ORDER BY COUNT(*) DESC", (since_iso,)).fetchall()
    return [(r[0], r[1]) for r in rows]


def review_status_counts() -> dict:
    """Antal review_queue-rækker pr. status — pass1 = alle, pass2 = ikke-pending."""
    with _db() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) FROM review_queue GROUP BY status").fetchall()
    return {r[0]: r[1] for r in rows}


def message_count(stream: str, since_iso: str) -> int:
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM aula_messages WHERE stream=? AND received_at>=?",
            (stream, since_iso)).fetchone()
    return row[0]


def last_message_at(stream: str) -> str | None:
    """Seneste modtagne mail i en stream — DRIFT-footerens sync-tidsstempel."""
    with _db() as con:
        row = con.execute(
            "SELECT MAX(received_at) FROM aula_messages WHERE stream=?",
            (stream,),
        ).fetchone()
    return row[0]


# ── Data-flywheel: parseren lærer af egne rettede/bekræftede beskeder ──
# Kun bruger-BEKRÆFTEDE (confirm-Opret) eller 32b-KORRIGEREDE resultater
# logges her — aldrig et ubekræftet straks-gæt, der kan være tavst forkert.
# recent_parse_examples fodres tilbage som few-shot i llm.parse_message.
_PARSE_EXAMPLES_CAP = 200


def add_parse_example(source_text: str, result: dict) -> None:
    """Fire-and-forget. Dedupe pr. source_text (nyeste vinder) og beskær til cap."""
    st = (source_text or "").strip()
    if not st:
        return
    try:
        with _db() as con:
            con.execute("DELETE FROM parse_examples WHERE source_text=?", (st,))
            con.execute(
                "INSERT INTO parse_examples(source_text,result_json,created_at) VALUES(?,?,?)",
                (st, json.dumps(result, ensure_ascii=False), datetime_now_iso()))
            con.execute(
                "DELETE FROM parse_examples WHERE id NOT IN "
                "(SELECT id FROM parse_examples ORDER BY id DESC LIMIT ?)",
                (_PARSE_EXAMPLES_CAP,))
    except sqlite3.Error:
        pass


def recent_parse_examples(limit: int = 4) -> list[dict]:
    if limit <= 0:
        return []
    with _db() as con:
        rows = con.execute(
            "SELECT source_text, result_json FROM parse_examples ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    return [{"source_text": r[0], "result": json.loads(r[1])} for r in rows]


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
              "stream", "importance", "sender_kind", "deferred_until")


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
                     resolved_at: str | None = None,
                     deferred_until: str | None = None) -> None:
    with _db() as con:
        con.execute(
            "UPDATE aula_items SET status=?, "
            "gcal_event_id=COALESCE(?, gcal_event_id), "
            "vikunja_task_id=COALESCE(?, vikunja_task_id), "
            "resolved_at=COALESCE(?, resolved_at), "
            "deferred_until=COALESCE(?, deferred_until) WHERE id=?",
            (status, gcal_event_id, vikunja_task_id, resolved_at,
             deferred_until, item_id),
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
    """Digest-input for both streams. Rows a user has panel-deferred ('Senere')
    have deferred_until set and are excluded permanently — by 06:30 the
    deferral itself has always lapsed, so checking it here would not help;
    the presence of the timestamp is what marks the item as panel-owned.
    Only inbox items ever carry a deferred_until, so this is a no-op for the
    aula stream."""
    with _db() as con:
        rows = con.execute(
            f"SELECT {','.join(_ITEM_COLS)} FROM aula_items "
            "WHERE intent='info' AND status='pending' AND stream=? "
            "AND deferred_until IS NULL "
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


def aula_archive_newsletters(resolved_at: str, stream: str = "inbox") -> int:
    """Panelets 'Arkivér alle' på nyhedsbreve: kun pending, kun nyhedsbrev."""
    with _db() as con:
        cur = con.execute(
            "UPDATE aula_items SET status='rejected', resolved_at=? "
            "WHERE status='pending' AND stream=? AND sender_kind='nyhedsbrev'",
            (resolved_at, stream),
        )
        return cur.rowcount


def aula_feed(since_iso: str, today_iso: str, stream: str = "aula") -> dict:
    """Dashboard block: info items + recent proposals/autos with status."""
    with _db() as con:
        info = con.execute(
            "SELECT id, title, summary, created_at, status, importance, "
            "sender_kind, deferred_until "
            "FROM aula_items WHERE intent='info' AND created_at >= ? AND stream=? "
            "ORDER BY created_at DESC",
            (since_iso, stream),
        ).fetchall()
        recent = con.execute(
            "SELECT id, title, intent, status, date, time, created_at, deadline, "
            "importance, sender_kind, deferred_until FROM aula_items "
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
        "info": [{"id": r[0], "title": r[1], "summary": r[2], "created_at": r[3],
                  "status": r[4], "importance": r[5], "sender_kind": r[6],
                  "deferred_until": r[7]}
                 for r in info],
        "recent": [{"id": r[0], "title": r[1], "intent": r[2], "status": r[3],
                    "date": r[4], "time": r[5], "created_at": r[6],
                    "deadline": r[7], "importance": r[8], "sender_kind": r[9],
                    "deferred_until": r[10]} for r in recent],
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

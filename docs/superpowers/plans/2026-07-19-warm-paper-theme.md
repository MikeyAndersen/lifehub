# Warm Paper Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the URL-selected "Warm Paper" secondary theme: three new routes (`/paper/tablet`, `/paper/wallpaper`, `/paper/panel`) with a separate React component tree, plus four additive brain features (shopping block, triage actions, newsletter bulk-archive, panel status feed).

**Architecture:** Separate presentational tree under `dashboard/src/components/paper/` sharing the existing data layer (`lib/api.js`, `lib/format.js`, `lib/mock.js`). All Warm Paper tokens live in `dashboard/src/styles/paper.css`, imported only by the three new Astro pages. Backend changes are additive endpoints/columns in `brain/`; the Telegram flow's semantics stay the source of truth (endpoints call the same `aula.*` functions).

**Tech Stack:** Astro 5 + React 18 (frontend), FastAPI + SQLite (brain), pytest (new, backend tests), `node --test` (new, frontend pure-logic tests — zero new npm deps).

**Spec:** `docs/superpowers/specs/2026-07-19-warm-paper-theme-design.md` — read it first.

## Global Constraints

- Space theme untouched: no edits to existing pages, space components, or `global.css`.
- Palette (verbatim): paper `#f4f0e8` (tablet/panel) / `#f1ede4` (ultrawide); ink `#2a2520`; secondary `#55493d`; muted `#7a7267`; faint `#b6ada0`; accent `#b95c38`, dark `#93482c`, tint `rgba(185,92,56,.12)`; status green `#5c8a5a`, amber `#c9a23c`; hairlines `rgba(42,37,32,.10)`–`.14`. Night: bg `#211d19`, text `#e8e0d3`/`#bdb2a0`, accent `#c98a67`.
- Typography: Instrument Sans 400/500/600 for UI; IBM Plex Mono for labels/meta/data, UPPERCASE, letter-spacing `.14em`–`.18em`; `font-feature-settings:'tnum'` on all clocks. Danish, sentence case content.
- No icons except status dots and task circles; **no emoji anywhere** (strip them from data).
- Accent = urgency/today only. One accent per theme.
- `@media (prefers-reduced-motion: reduce)` disables all drift/sway/breathe animations.
- Finance must never appear on any paper surface. Wallpaper uses the ambient document (never `post`).
- Min text sizes: tablet ≈ 32px @2560; panel ≈ 13px mono / 16px body @1920.
- Backend endpoints that mutate are admin-gated identically to `/api/brief/regenerate` (Cf-Access header email in `config.ADMIN_EMAILS`).
- Python style: match `brain/app/*` — Danish comments where neighbors have them, type hints, `log = logging.getLogger("lifehub")`.
- Commit after every task (messages below).

---

### Task 1: Backend test infra + shopping block

**Files:**
- Create: `brain/tests/__init__.py` (empty)
- Create: `brain/tests/conftest.py`
- Create: `brain/tests/test_shopping_block.py`
- Modify: `brain/requirements.txt` (append pytest)
- Modify: `brain/app/dashboard.py` (add `refresh_shopping`, extend `build`)
- Modify: `brain/app/main.py` (schedule + boot-warm the new job)

**Interfaces:**
- Consumes: `vikunja.shopping_inventory()` → `list[dict]` with keys `name, raw_title, done, bucket, vikunja_task_id, updated_at`; `store.set_cache/get_cache_meta`.
- Produces: dashboard document key `shopping: {"items": [{"id": int, "title": str}], "stale": bool}` present only when `ambient=False` and the cache exists. Frontend (Task 8) relies on exactly this shape.

- [ ] **Step 1: Add pytest to requirements and install**

Append one line to `brain/requirements.txt`:

```
pytest>=8.0
```

Run: `cd brain && pip install pytest`
Expected: `Successfully installed pytest-...` (or already satisfied).

- [ ] **Step 2: Write conftest with an isolated temp DB**

`brain/tests/conftest.py`:

```python
"""Test-harness: hver test får sin egen SQLite-fil, så store.init() aldrig
rører den rigtige lifehub.db. DB_PATH skal sættes FØR app.config importeres."""
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="lifehub-test-")
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")


@pytest.fixture()
def db():
    from app import config, store
    # Frisk fil pr. test — filnavnet roteres så CREATE TABLE kører igen.
    config.DB_PATH = os.path.join(_tmp, f"test-{os.urandom(4).hex()}.db")
    store.init()
    return store
```

- [ ] **Step 3: Write the failing test for the shopping block**

`brain/tests/test_shopping_block.py`:

```python
"""Shopping-blokken i dashboard-dokumentet (Warm Paper tablet INDKØB)."""
from app import dashboard


def test_build_includes_shopping_when_cached(db):
    db.set_cache("shopping", [{"id": 7, "title": "Mælk"}, {"id": 9, "title": "Rugbrød"}])
    doc = dashboard.build(None, ambient=False)
    assert doc["shopping"]["items"] == [{"id": 7, "title": "Mælk"},
                                        {"id": 9, "title": "Rugbrød"}]
    assert doc["shopping"]["stale"] is False


def test_ambient_doc_never_has_shopping(db):
    db.set_cache("shopping", [{"id": 7, "title": "Mælk"}])
    doc = dashboard.build(None, ambient=True)
    assert "shopping" not in doc


def test_no_cache_no_block(db):
    doc = dashboard.build(None, ambient=False)
    assert "shopping" not in doc
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd brain && python -m pytest tests/test_shopping_block.py -v`
Expected: FAIL — `KeyError: 'shopping'` (build doesn't produce the block yet).

- [ ] **Step 5: Implement refresh job + doc block**

In `brain/app/dashboard.py`, after `refresh_beholdning` add:

```python
# Indkøbslisten (Warm Paper §backend 1): åbne tasks i Vikunja-indkøbsprojektet.
SHOPPING_STALE_S = 30 * 60


async def refresh_shopping() -> None:
    try:
        inv = await vikunja.shopping_inventory()
        store.set_cache("shopping", [
            {"id": i["vikunja_task_id"], "title": i["raw_title"]}
            for i in inv if i["bucket"] == "open"
        ])
    except Exception:
        log.exception("shopping refresh failed")
```

In `build()`, right after the `beholdning` block (before `if config.GMAIL_ENABLED:`) add:

```python
    # Indkøb (Warm Paper): kun på interaktive flader — ambient får den ikke.
    if not ambient:
        shop = store.get_cache_meta("shopping")
        if shop is not None:
            items, updated_at = shop
            doc["shopping"] = {
                "items": items,
                "stale": (time.time() - updated_at) > SHOPPING_STALE_S,
            }
```

In `brain/app/main.py` `lifespan()`: after the `refresh_beholdning` `add_job` line add

```python
    scheduler.add_job(dashboard.refresh_shopping, "interval", minutes=5, jitter=30)
```

and add `dashboard.refresh_shopping` to the boot-warm tuple (the `for job in (...)` loop).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd brain && python -m pytest tests/ -v`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add brain/requirements.txt brain/tests brain/app/dashboard.py brain/app/main.py
git commit -m "Warm Paper backend: shopping-blok i dashboard-dokumentet + pytest-infra"
```

---

### Task 2: `deferred_until` column, item ids in the feed, defer filtering

**Files:**
- Create: `brain/tests/test_defer_feed.py`
- Modify: `brain/app/store.py` (migration, `aula_update_item`, `aula_feed`)
- Modify: `brain/app/triage.py` (`feed` filters deferred items)

**Interfaces:**
- Consumes: existing `store.aula_insert_item`, `store.aula_feed(since_iso, today_iso, stream)`.
- Produces: `aula_items.deferred_until TEXT` column; `store.aula_update_item(..., deferred_until: str | None = None)`; feed rows (both `info` and `recent`) now include `"id": int` and `"deferred_until": str | None`; `triage.feed(days)` drops pending rows whose `deferred_until` is in the future. Task 3 (defer action) and Task 10 (panel needs `id`) rely on this.

- [ ] **Step 1: Write the failing tests**

`brain/tests/test_defer_feed.py`:

```python
"""Defer-mekanik (panelets 'Senere'): pending + deferred_until i fremtiden
skjules i triage.feed; når fristen er passeret dukker emnet op igen."""
from datetime import datetime, timedelta

from app import triage


def _insert(store, title, *, intent="handling", deferred_until=None):
    item_id = store.aula_insert_item(
        "msg-1", intent=intent, title=title, summary="s", date=None, time=None,
        all_day=False, deadline=None, confidence=0.9, ambiguity_flags=[],
        created_at=datetime.now().isoformat(timespec="seconds"),
        stream="inbox", importance="normal", sender_kind="andet")
    if deferred_until:
        store.aula_update_item(item_id, status="pending",
                               deferred_until=deferred_until)
    return item_id


def test_feed_rows_carry_id_and_deferred_until(db):
    item_id = _insert(db, "Betal elregning")
    feed = triage.feed(days=7)
    row = next(r for r in feed["recent"] if r["title"] == "Betal elregning")
    assert row["id"] == item_id
    assert row["deferred_until"] is None


def test_deferred_item_hidden_until_tomorrow(db):
    tomorrow = (datetime.now() + timedelta(days=1)).replace(microsecond=0)
    _insert(db, "Skjult til i morgen", deferred_until=tomorrow.isoformat())
    feed = triage.feed(days=7)
    assert all(r["title"] != "Skjult til i morgen" for r in feed["recent"])


def test_expired_defer_reappears(db):
    yesterday = (datetime.now() - timedelta(days=1)).replace(microsecond=0)
    _insert(db, "Tilbage igen", deferred_until=yesterday.isoformat())
    feed = triage.feed(days=7)
    assert any(r["title"] == "Tilbage igen" for r in feed["recent"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd brain && python -m pytest tests/test_defer_feed.py -v`
Expected: FAIL — `TypeError: aula_update_item() got an unexpected keyword argument 'deferred_until'` and/or `KeyError: 'id'`.

- [ ] **Step 3: Implement store changes**

In `brain/app/store.py`:

1. Append to the `_MIGRATIONS` list (after the `sender_kind` line):

```python
    "ALTER TABLE aula_items ADD COLUMN deferred_until TEXT",
```

2. Append `"deferred_until"` to the `_ITEM_COLS` tuple (around line 342) — without this, `aula_get_item`/`_item_row` never return the new column:

```python
_ITEM_COLS = ("id", "message_id", "intent", "title", "summary", "date", "time",
              "all_day", "deadline", "confidence", "ambiguity_flags", "status",
              "gcal_event_id", "vikunja_task_id", "created_at", "resolved_at",
              "stream", "importance", "sender_kind", "deferred_until")
```

3. Extend `aula_update_item`:

```python
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
```

4. In `aula_feed`, add `id` and `deferred_until` to both SELECTs and dicts:

```python
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
```

5. In `brain/app/triage.py`, replace `feed`:

```python
def feed(days: int = 7) -> dict:
    now = datetime.now(_tz())
    doc = store.aula_feed((now - timedelta(days=days)).isoformat(timespec="seconds"),
                          now.date().isoformat(), stream=_STREAM)
    # 'Senere' i panelet: pending emner med deferred_until i fremtiden skjules
    # (også i space-temaets Post-widget — udsat betyder udsat overalt).
    now_iso = now.isoformat(timespec="seconds")

    def visible(row: dict) -> bool:
        return not (row["status"] == "pending" and row.get("deferred_until")
                    and row["deferred_until"] > now_iso)

    doc["info"] = [r for r in doc["info"] if visible(r)]
    doc["recent"] = [r for r in doc["recent"] if visible(r)]
    return doc
```

Note the comparison is string-vs-string on local-time ISO stamps (same convention as the rest of the module — `deferred_until` is always written by Task 3 as a naive local ISO string).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd brain && python -m pytest tests/ -v`
Expected: all PASS (including Task 1 tests).

- [ ] **Step 5: Commit**

```bash
git add brain/app/store.py brain/app/triage.py brain/tests/test_defer_feed.py
git commit -m "Warm Paper backend: deferred_until-kolonne, feed-ids og defer-filtrering"
```

---

### Task 3: Triage action endpoints (approve / archive / defer / archive-newsletters)

**Files:**
- Create: `brain/app/post_actions.py`
- Create: `brain/tests/test_post_actions.py`
- Modify: `brain/app/store.py` (add `aula_archive_newsletters`)
- Modify: `brain/app/main.py` (two endpoints)

**Interfaces:**
- Consumes: `aula.approve_item(item_id) -> str | None` (async), `aula.reject_item(item_id) -> bool`, `store.aula_get_item`, `store.aula_update_item(..., deferred_until=...)` from Task 2.
- Produces:
  - `post_actions.apply(item_id: int, action: str) -> dict` (async) — raises `post_actions.ActionError(status_code, detail)` on failure; returns `{"ok": True, "receipt": str | None}`.
  - `store.aula_archive_newsletters(resolved_at: str, stream: str = "inbox") -> int`.
  - HTTP: `POST /api/post/{item_id}/action` body `{"action": "approve"|"archive"|"defer"}`; `POST /api/post/archive-newsletters` → `{"ok": True, "archived": int}`. Both admin-gated. Task 10's frontend calls exactly these.

- [ ] **Step 1: Write the failing tests**

`brain/tests/test_post_actions.py`:

```python
"""Panel-handlinger: approve/arkivér/udsæt + nyhedsbrevs-bulk. Vikunja/gcal
mockes — semantikken (statusser) er det, der testes."""
from datetime import datetime

import pytest

from app import post_actions


def _insert(store, *, intent="handling", sender_kind="andet", status=None):
    item_id = store.aula_insert_item(
        "msg-1", intent=intent, title="Betal elregning", summary="s",
        date=None, time=None, all_day=False, deadline=None, confidence=0.9,
        ambiguity_flags=[], created_at=datetime.now().isoformat(timespec="seconds"),
        stream="inbox", importance="normal", sender_kind=sender_kind)
    if status:
        store.aula_update_item(item_id, status=status)
    return item_id


@pytest.mark.asyncio
async def test_approve_delegates_to_aula(db, monkeypatch):
    called = {}

    async def fake_approve(item_id):
        called["id"] = item_id
        return "✅ Opgave oprettet: Betal elregning"

    monkeypatch.setattr(post_actions.aula, "approve_item", fake_approve)
    item_id = _insert(db)
    result = await post_actions.apply(item_id, "approve")
    assert called["id"] == item_id
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_archive_rejects_item(db):
    item_id = _insert(db)
    result = await post_actions.apply(item_id, "archive")
    assert result["ok"] is True
    assert db.aula_get_item(item_id)["status"] == "rejected"


@pytest.mark.asyncio
async def test_defer_sets_tomorrow_and_keeps_pending(db):
    item_id = _insert(db)
    await post_actions.apply(item_id, "defer")
    item = db.aula_get_item(item_id)
    assert item["status"] == "pending"
    assert item["deferred_until"] > datetime.now().isoformat(timespec="seconds")


@pytest.mark.asyncio
async def test_unknown_action_and_wrong_stream_rejected(db):
    item_id = _insert(db)
    with pytest.raises(post_actions.ActionError) as exc:
        await post_actions.apply(item_id, "explode")
    assert exc.value.status_code == 422
    with pytest.raises(post_actions.ActionError) as exc:
        await post_actions.apply(999999, "archive")
    assert exc.value.status_code == 404


def test_archive_newsletters_only_hits_pending_nyhedsbrev(db):
    a = _insert(db, intent="info", sender_kind="nyhedsbrev")
    b = _insert(db, intent="info", sender_kind="nyhedsbrev", status="briefed")
    c = _insert(db, intent="info", sender_kind="kommune")
    n = db.aula_archive_newsletters(datetime.now().isoformat(timespec="seconds"))
    assert n == 1
    assert db.aula_get_item(a)["status"] == "rejected"
    assert db.aula_get_item(b)["status"] == "briefed"
    assert db.aula_get_item(c)["status"] == "pending"
```

Also append to `brain/requirements.txt`:

```
pytest-asyncio>=0.23
```

and create `brain/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
```

Run: `cd brain && pip install pytest-asyncio`

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd brain && python -m pytest tests/test_post_actions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.post_actions'`.

- [ ] **Step 3: Implement `post_actions.py` and the store helper**

`brain/app/post_actions.py`:

```python
"""Panel-handlinger på post-triage-emner (Warm Paper handlingspanel).

Tynd delegering: semantikken ejes af aula.approve_item/reject_item — de samme
funktioner som Telegram-knapperne kalder. Modulet tilføjer kun 'defer' og
stream-vagten (kun inbox-emner kan rammes herfra)."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import aula, config, store


class ActionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def apply(item_id: int, action: str) -> dict:
    item = store.aula_get_item(item_id)
    if item is None or item.get("stream") != "inbox":
        raise ActionError(404, "Ukendt post-emne")
    if action == "approve":
        receipt = await aula.approve_item(item_id)
        if receipt is None:
            raise ActionError(409, "Emnet kan ikke godkendes (ikke pending?)")
        return {"ok": True, "receipt": receipt}
    if action == "archive":
        if item["status"] != "pending":
            raise ActionError(409, "Emnet er allerede afgjort")
        store.aula_update_item(
            item_id, status="rejected",
            resolved_at=datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds"))
        return {"ok": True, "receipt": None}
    if action == "defer":
        if item["status"] != "pending":
            raise ActionError(409, "Emnet er allerede afgjort")
        tomorrow = datetime.now(ZoneInfo(config.TZ)).date() + timedelta(days=1)
        store.aula_update_item(item_id, status="pending",
                               deferred_until=f"{tomorrow.isoformat()}T00:00:00")
        return {"ok": True, "receipt": None}
    raise ActionError(422, f"Ukendt handling: {action}")
```

(Archive is done directly via `store.aula_update_item` rather than `aula.reject_item` so info-items — which `reject_item` also accepts, but whose semantics we want to keep explicit — follow one code path with one status check.)

In `brain/app/store.py`, after `aula_expired_since` add:

```python
def aula_archive_newsletters(resolved_at: str, stream: str = "inbox") -> int:
    """Panelets 'Arkivér alle' på nyhedsbreve: kun pending, kun nyhedsbrev."""
    with _db() as con:
        cur = con.execute(
            "UPDATE aula_items SET status='rejected', resolved_at=? "
            "WHERE status='pending' AND stream=? AND sender_kind='nyhedsbrev'",
            (resolved_at, stream),
        )
        return cur.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd brain && python -m pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Add the HTTP endpoints**

In `brain/app/main.py`: add `post_actions` to the `from . import ...` line, then after `api_post_poll` add:

```python
@app.post("/api/post/{item_id}/action")
async def api_post_action(item_id: int, request: Request) -> dict:
    """Warm Paper-panelets pille-handlinger. Admin-gated som brief/regenerate;
    semantikken ejes af aula.approve_item/reject-flowet (post_actions)."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = body.get("action") if isinstance(body, dict) else None
    try:
        return await post_actions.apply(item_id, action or "")
    except post_actions.ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/api/post/archive-newsletters")
async def api_post_archive_newsletters(request: Request) -> dict:
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds")
    return {"ok": True, "archived": store.aula_archive_newsletters(now)}
```

(Put the two imports at top of file instead if `datetime`/`ZoneInfo` are already imported there — check first; `main.py` currently imports neither.)

- [ ] **Step 6: Verify the app still imports and tests pass**

Run: `cd brain && python -c "from app import main" && python -m pytest tests/ -v`
Expected: no import error; all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add brain/app/post_actions.py brain/app/main.py brain/app/store.py brain/tests/test_post_actions.py brain/pytest.ini brain/requirements.txt
git commit -m "Warm Paper backend: post-handlinger (godkend/arkivér/udsæt) + nyhedsbrevs-bulk"
```

---

### Task 4: Panel status feed (`GET /api/panel/status`)

**Files:**
- Create: `brain/app/panel_status.py`
- Create: `brain/tests/test_panel_status.py`
- Modify: `brain/app/store.py` (add `last_message_at`)
- Modify: `brain/app/main.py` (endpoint)

**Interfaces:**
- Consumes: `store.get_cache_meta(key) -> tuple[payload, updated_at] | None`, new `store.last_message_at(stream) -> str | None`, `config.OLLAMA_URL`-style config (check `brain/app/config.py` for the exact Ollama base-URL variable name before coding — `grep -n OLLAMA brain/app/config.py`).
- Produces: `panel_status.build() -> dict` (async): `{"generated_at": iso, "services": [{"name": str, "state": "ok"|"warn"|"off", "detail": str}]}`. Pure helper `age_state(age_s: float | None, warn_after_s: float) -> str`. Frontend Task 10 renders `services` verbatim and computes brain latency from its own fetch timing.

- [ ] **Step 1: Write the failing tests**

`brain/tests/test_panel_status.py`:

```python
"""DRIFT-footerens tilstandslogik. Kun de deterministiske dele testes —
ollama-ping mockes."""
import time

from app import panel_status


def test_age_state_thresholds():
    assert panel_status.age_state(60, warn_after_s=900) == "ok"
    assert panel_status.age_state(901, warn_after_s=900) == "warn"
    assert panel_status.age_state(None, warn_after_s=900) == "off"


async def test_build_reports_cache_ages(db, monkeypatch):
    async def fake_ping():
        return True

    monkeypatch.setattr(panel_status, "_ollama_ok", fake_ping)
    db.set_cache("tasks", [])
    doc = await panel_status.build()
    names = [s["name"] for s in doc["services"]]
    assert "vikunja" in names and "ollama" in names
    vik = next(s for s in doc["services"] if s["name"] == "vikunja")
    assert vik["state"] == "ok"
    assert vik["detail"].startswith("sync ")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd brain && python -m pytest tests/test_panel_status.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.panel_status'`.

- [ ] **Step 3: Implement store helper + module**

In `brain/app/store.py` near `message_count` add:

```python
def last_message_at(stream: str) -> str | None:
    """Seneste modtagne mail i en stream — DRIFT-footerens sync-tidsstempel."""
    with _db() as con:
        row = con.execute(
            "SELECT MAX(received_at) FROM aula_messages WHERE stream=?",
            (stream,),
        ).fetchone()
    return row[0]
```

`brain/app/panel_status.py`:

```python
"""DRIFT-footer til Warm Paper-panelet: reelle metrikker, aldrig opfundne.

Hver tjeneste rapporteres som {name, state, detail}:
  ok   = data friskt nok
  warn = data ældre end tærsklen (tjenesten hangler formentlig)
  off  = intet datagrundlag (endnu) — frontenden viser den dæmpet
Ollama pinges let (2 s timeout) og caches 60 s, så panel-polling aldrig
belaster GPU-boksen."""
from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from . import config, store

_ollama_cache: tuple[float, bool] | None = None


def age_state(age_s: float | None, warn_after_s: float) -> str:
    if age_s is None:
        return "off"
    return "ok" if age_s <= warn_after_s else "warn"


def _hhmm(ts: float) -> str:
    return datetime.fromtimestamp(ts, ZoneInfo(config.TZ)).strftime("%H:%M")


def _cache_row(name: str, key: str, warn_after_s: float) -> dict:
    meta = store.get_cache_meta(key)
    if meta is None:
        return {"name": name, "state": "off", "detail": "ingen data"}
    updated_at = meta[1]
    state = age_state(time.time() - updated_at, warn_after_s)
    detail = f"sync {_hhmm(updated_at)}"
    if state == "warn":
        detail += " · forsinket"
    return {"name": name, "state": state, "detail": detail}


def _mail_row(name: str, stream: str, enabled: bool) -> dict:
    if not enabled:
        return {"name": name, "state": "off", "detail": "slået fra"}
    last = store.last_message_at(stream)
    if last is None:
        return {"name": name, "state": "ok", "detail": "ingen mails endnu"}
    # received_at er lokal ISO — sidste mail kan naturligt være gammel, så
    # mail-rækker warner aldrig på alder alene; de viser blot tidspunktet.
    return {"name": name, "state": "ok", "detail": f"seneste {last[11:16]}"}


async def _ollama_ok() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{config.OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def _ollama_row() -> dict:
    global _ollama_cache
    now = time.monotonic()
    if _ollama_cache is None or now - _ollama_cache[0] > 60:
        _ollama_cache = (now, await _ollama_ok())
    ok = _ollama_cache[1]
    return {"name": "ollama", "state": "ok" if ok else "warn",
            "detail": config.OLLAMA_MODEL if ok else "svarer ikke"}


async def build() -> dict:
    services = [
        _cache_row("vikunja", "tasks", warn_after_s=15 * 60),
        _cache_row("kalender", "events", warn_after_s=15 * 60),
        _cache_row("vejr", "weather", warn_after_s=90 * 60),
        _cache_row("madplan", "madplan", warn_after_s=config.MADPLAN_STALE_MINUTES * 60),
        _mail_row("gmail-triage", "inbox", config.TRIAGE_ENABLED),
        _mail_row("aula", "aula", config.GMAIL_ENABLED),
        await _ollama_row(),
    ]
    return {"generated_at": datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds"),
            "services": services}
```

**Before writing this file:** run `grep -n "OLLAMA" brain/app/config.py` and use the real base-URL/model variable names (the plan assumes `OLLAMA_URL` and `OLLAMA_MODEL`; adjust if they differ, e.g. `OLLAMA_BASE_URL`). Also confirm `MADPLAN_STALE_MINUTES` exists (it does — used in `dashboard.py`).

In `brain/app/main.py`: add `panel_status` to the `from . import ...` line and add:

```python
@app.get("/api/panel/status")
async def api_panel_status(request: Request) -> dict:
    """DRIFT-footer til Warm Paper-panelet. Admin-gated: driftsdata er ufarligt
    men panelet er en admin-flade, så samme regel som resten."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    return await panel_status.build()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd brain && python -m pytest tests/ -v && python -c "from app import main"`
Expected: all PASS, clean import.

- [ ] **Step 5: Commit**

```bash
git add brain/app/panel_status.py brain/app/store.py brain/app/main.py brain/tests/test_panel_status.py
git commit -m "Warm Paper backend: /api/panel/status — DRIFT-footer med reelle metrikker"
```

---

### Task 5: Instrument Sans fonts + `paper.css`

**Files:**
- Create: `dashboard/public/fonts/instrument-sans-400.woff2`, `-500.woff2`, `-600.woff2` (downloaded)
- Create: `dashboard/src/styles/paper.css`

**Interfaces:**
- Produces: CSS custom properties on `.paper-root` (all listed below) and keyframes `lh-drift-a`, `lh-drift-b`, `lh-sway`, `lh-breathe`. Every paper component (Tasks 8–10) styles itself exclusively from these variables and utility classes. Night mode = `.paper-root[data-mode="night"]`.

- [ ] **Step 1: Download the fonts (latin subset, woff2)**

Run from repo root (Bash tool):

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
for w in 400 500 600; do
  url=$(curl -s -A "$UA" "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@$w&display=swap" | grep -o "https://[^)]*\.woff2" | head -1)
  curl -s "$url" -o "dashboard/public/fonts/instrument-sans-$w.woff2"
done
ls -la dashboard/public/fonts/instrument-sans-*
```

Expected: three files, each > 10 KB. If any file is tiny/HTML, the UA sniffing failed — retry, or fall back to downloading from https://github.com/Instrument/instrument-sans (official repo, OFL-licensed) and convert.

- [ ] **Step 2: Write `dashboard/src/styles/paper.css`**

```css
/* ═══════════════════════════════════════════════════════════════
   Warm Paper — sekundært tema (spec: docs/superpowers/specs/
   2026-07-19-warm-paper-theme-design.md, mockups 1d–1g).
   Importeres KUN af /paper/*-siderne. Space-temaet rører aldrig
   denne fil eller disse fonte.
   ═══════════════════════════════════════════════════════════════ */

@font-face {
  font-family: 'Instrument Sans';
  src: url('/fonts/instrument-sans-400.woff2') format('woff2');
  font-weight: 400; font-display: swap;
}
@font-face {
  font-family: 'Instrument Sans';
  src: url('/fonts/instrument-sans-500.woff2') format('woff2');
  font-weight: 500; font-display: swap;
}
@font-face {
  font-family: 'Instrument Sans';
  src: url('/fonts/instrument-sans-600.woff2') format('woff2');
  font-weight: 600; font-display: swap;
}

.paper-root {
  /* — dagpalet (mockup 1d/1g) — */
  --paper-bg: #f4f0e8;          /* ultrawide sætter selv #f1ede4 */
  --ink: #2a2520;
  --ink-2: #55493d;
  --muted: #7a7267;
  --faint: #b6ada0;
  --accent: #b95c38;
  --accent-dark: #93482c;
  --accent-tint: rgba(185, 92, 56, .12);
  --ok: #5c8a5a;
  --warn: #c9a23c;
  --hairline: rgba(42, 37, 32, .10);
  --hairline-strong: rgba(42, 37, 32, .14);
  --circle-idle: #c9c1b4;       /* opgavecirkler uden hast */
  --done-fill: #e2dccf;
  --side-opacity: 1;

  --font-ui: 'Instrument Sans', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;

  /* Motion (kun wallpaper bruger drift; produktion ≥300 s pr. krydsning —
     mockuppens 60–90 s er demo). --drift-base kan overstyres via ?drift= . */
  --drift-base: 320s;
  --sway-a: 90s;
  --sway-b: 110s;

  background: var(--paper-bg);
  color: var(--ink);
  font-family: var(--font-ui);
  width: 100vw; height: 100vh; overflow: hidden;
  box-sizing: border-box;
}
.paper-root *, .paper-root *::before, .paper-root *::after { box-sizing: border-box; }

/* — natpalet (mockup 1e): samme variabler, nye værdier — */
.paper-root[data-mode="night"] {
  --paper-bg: #211d19;
  --ink: #e8e0d3;
  --ink-2: #bdb2a0;
  --muted: #8a7e6e;
  --faint: #5e564a;
  --accent: #c98a67;
  --accent-dark: #c98a67;
  --accent-tint: rgba(201, 138, 103, .14);
  --hairline: rgba(232, 224, 211, .08);
  --hairline-strong: rgba(232, 224, 211, .12);
  --circle-idle: #5e564a;
  --done-fill: #3a342c;
  --side-opacity: .75;
}

/* — fælles byggesten — */
.paper-mono {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: .16em;
}
.paper-clock { font-feature-settings: 'tnum'; font-variant-numeric: tabular-nums; }
.paper-pill {
  border: 2px solid var(--hairline-strong);
  border-radius: 999px;
  font-weight: 500;
}
.paper-badge {
  font-family: var(--font-mono);
  background: var(--accent-tint);
  color: var(--accent-dark);
  border-radius: 6px;
  padding: .1em .55em;
}
.paper-badge--neutral { background: rgba(42, 37, 32, .07); color: var(--muted); }
.paper-root[data-mode="night"] .paper-badge--neutral {
  background: rgba(232, 224, 211, .08);
}
.paper-dot { border-radius: 50%; flex: none; }

/* — motion (wallpaper + breathe-prik) — */
@keyframes lh-drift-a {
  from { transform: translateX(0); }
  to   { transform: translateX(5600px); }
}
@keyframes lh-drift-b {
  from { transform: translateX(5600px); }
  to   { transform: translateX(-1500px); }
}
@keyframes lh-sway {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(26px); }
}
@keyframes lh-breathe {
  0%, 100% { opacity: 1; }
  50%      { opacity: .35; }
}

@media (prefers-reduced-motion: reduce) {
  .paper-root [style*="lh-drift"], .paper-root [style*="lh-sway"],
  .paper-root [style*="lh-breathe"],
  .paper-drift, .paper-sway, .paper-breathe {
    animation: none !important;
  }
}
```

- [ ] **Step 3: Verify the build still passes**

Run: `cd dashboard && npm run build`
Expected: `astro build` completes with no errors (CSS is not yet imported anywhere — this confirms nothing broke).

- [ ] **Step 4: Commit**

```bash
git add dashboard/public/fonts/instrument-sans-400.woff2 dashboard/public/fonts/instrument-sans-500.woff2 dashboard/public/fonts/instrument-sans-600.woff2 dashboard/src/styles/paper.css
git commit -m "Warm Paper: Instrument Sans (self-hosted) + paper.css designtokens"
```

---

### Task 6: Pure logic — `paperLogic.js` + `paperNight.js` (node --test)

**Files:**
- Create: `dashboard/src/components/paper/paperLogic.js`
- Create: `dashboard/src/components/paper/paperNight.js`
- Create: `dashboard/test/paperLogic.test.mjs`
- Create: `dashboard/test/paperNight.test.mjs`
- Modify: `dashboard/package.json` (add test script)

**Interfaces:**
- Consumes: dashboard document shapes from `mock.js` (`events`, `tasks`, `aula`, `post`, `weather`, `shopping` from Task 1).
- Produces (Tasks 8–10 import these exact names):
  - `stripEmoji(s) -> string`
  - `classBadge(title) -> string | null` — "2.B"-style token or SFO, else null
  - `postBadge(item) -> {label: string, tone: 'accent'|'neutral'}`
  - `partitionInbox(post) -> {actionable: item[], newsletters: item[]}` — pending only
  - `primaryAction(item) -> {label: string, action: 'approve'|'archive'}`
  - `quietAction(item) -> {label: string, action: 'archive'|'defer'}`
  - `dueLine(iso, now) -> string | null` — "i dag inden 14:00" / "i morgen" / "ons 23.7." / "forfalden"
  - `pickHighlights(doc, now) -> [{text: string, urgent: bool}]` — max 2
  - `tomorrowOverview(doc, now) -> {line: string, tasks: task[]}`
  - `nextDays(events, now, n=3) -> [{weekday: string, badges: string[]}]`
  - `isNight(now, weather) -> bool` (from `paperNight.js`)

- [ ] **Step 1: Write the failing tests**

`dashboard/test/paperLogic.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  stripEmoji, classBadge, postBadge, partitionInbox, primaryAction,
  quietAction, dueLine, pickHighlights, nextDays,
} from '../src/components/paper/paperLogic.js';

const at = (off, hh, mm = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + off); d.setHours(hh, mm, 0, 0);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(hh)}:${p(mm)}:00`;
};

test('stripEmoji fjerner emoji men bevarer dansk tekst', () => {
  assert.equal(stripEmoji('Fødselsdagsgave 🎁'), 'Fødselsdagsgave');
  assert.equal(stripEmoji('Æg og mælk'), 'Æg og mælk');
});

test('classBadge finder klassebetegnelser', () => {
  assert.equal(classBadge('Skovtur 2.B mandag'), '2.B');
  assert.equal(classBadge('SFO lukker kl. 15'), 'SFO');
  assert.equal(classBadge('Ugens bogstav er S'), null);
});

test('postBadge mapper sender_kind og tone', () => {
  assert.deepEqual(postBadge({ sender_kind: 'bank', importance: 'high' }),
                   { label: 'BANK', tone: 'accent' });
  assert.deepEqual(postBadge({ sender_kind: 'nyhedsbrev', importance: 'low' }),
                   { label: 'LAV PRIORITET', tone: 'neutral' });
  assert.deepEqual(postBadge({ sender_kind: 'andet', importance: 'normal' }),
                   { label: 'INFO', tone: 'neutral' });
});

test('partitionInbox deler pending i handlinger og nyhedsbreve', () => {
  const post = {
    info: [
      { id: 1, status: 'pending', sender_kind: 'nyhedsbrev', title: 'Ugens tilbud' },
      { id: 2, status: 'pending', sender_kind: 'kommune', title: 'Årsopgørelse' },
      { id: 3, status: 'briefed', sender_kind: 'kommune', title: 'Gammel' },
    ],
    recent: [
      { id: 4, status: 'pending', intent: 'handling', sender_kind: 'forsikring', title: 'Forny' },
      { id: 5, status: 'approved', intent: 'handling', sender_kind: 'bank', title: 'Betalt' },
    ],
  };
  const { actionable, newsletters } = partitionInbox(post);
  assert.deepEqual(actionable.map((i) => i.id), [4, 2]);
  assert.deepEqual(newsletters.map((i) => i.id), [1]);
});

test('primary/quiet action afhænger af intent', () => {
  const handling = { intent: 'handling', title: 'Betal elregning' };
  const info = { sender_kind: 'kommune', title: 'Ny info' };
  assert.deepEqual(primaryAction(handling), { label: 'Opret opgave: Betal elregning', action: 'approve' });
  assert.deepEqual(quietAction(handling), { label: 'Arkivér', action: 'archive' });
  assert.deepEqual(primaryAction(info), { label: 'Læs & kvittér', action: 'archive' });
  assert.deepEqual(quietAction(info), { label: 'Senere', action: 'defer' });
});

test('dueLine på dansk', () => {
  const now = new Date();
  assert.equal(dueLine(at(0, 14), now), 'i dag inden 14:00');
  assert.equal(dueLine(at(1, 17), now), 'i morgen');
  assert.equal(dueLine(at(-1, 12), now), 'forfalden');
  assert.equal(dueLine(null, now), null);
});

test('pickHighlights: kommende event i dag først, maks 2', () => {
  const now = new Date(); now.setHours(10, 0, 0, 0);
  const doc = {
    events: [{ title: 'Svømning — Alma', start: at(0, 16), all_day: false }],
    tasks: [{ id: 1, title: 'Køb gave', due: at(0, 14) }],
    aula: { recent: [] },
  };
  const hl = pickHighlights(doc, now);
  assert.equal(hl.length, 2);
  assert.match(hl[0].text, /Svømning — Alma kl\. 16:00/);
  assert.equal(hl[0].urgent, true);
});

test('nextDays grupperer 3 kommende dage', () => {
  const now = new Date();
  const days = nextDays([
    { title: 'Tandlæge', start: at(1, 9), all_day: false },
    { title: 'Cykeltur', start: at(2, 10), all_day: false },
  ], now, 3);
  assert.equal(days.length, 3);
  assert.deepEqual(days[0].badges, ['Tandlæge']);
  assert.deepEqual(days[2].badges, []);
});
```

`dashboard/test/paperNight.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isNight } from '../src/components/paper/paperNight.js';

const todayAt = (hh, mm = 0) => {
  const d = new Date(); d.setHours(hh, mm, 0, 0);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(hh)}:${p(mm)}:00`;
};
const weather = { sunrise: todayAt(4, 40), sunset: todayAt(21, 45) };
const clock = (hh, mm = 0) => { const d = new Date(); d.setHours(hh, mm, 0, 0); return d; };

test('dag mellem solopgang og solnedgang', () => {
  assert.equal(isNight(clock(12), weather), false);
  assert.equal(isNight(clock(21, 44), weather), false);
});

test('nat efter solnedgang og før solopgang', () => {
  assert.equal(isNight(clock(22), weather), true);
  assert.equal(isNight(clock(4, 0), weather), true);
});

test('fallback uden sol-tider: nat 22–06', () => {
  assert.equal(isNight(clock(23), null), true);
  assert.equal(isNight(clock(12), null), false);
});
```

In `dashboard/package.json` add to `"scripts"`:

```json
    "test": "node --test test/"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd dashboard && npm test`
Expected: FAIL — `Cannot find module ... paperLogic.js`.

- [ ] **Step 3: Implement the modules**

`dashboard/src/components/paper/paperNight.js`:

```js
/* Dag/nat for Warm Paper-tabletten: nat = efter solnedgang eller før
   solopgang (weather.sunrise/sunset, lokal ISO). Uden sol-tider: 22–06. */
const hourOf = (iso) => {
  const [h, m] = iso.slice(11, 16).split(':');
  return +h + +m / 60;
};

export function isNight(now, weather) {
  const t = now.getHours() + now.getMinutes() / 60;
  if (!weather?.sunrise || !weather?.sunset) return t >= 22 || t < 6;
  return t < hourOf(weather.sunrise) || t >= hourOf(weather.sunset);
}
```

`dashboard/src/components/paper/paperLogic.js`:

```js
/* Ren logik for Warm Paper-fladerne — ingen React, testes med node --test.
   Datoformer matcher brain-dokumentet (lokal ISO uden zone). */
import { fmtTime, isOverdue } from '../../lib/format.js';

/** Spec: ingen emoji på paper-flader — data kan indeholde dem (fx indkøb). */
export const stripEmoji = (s) =>
  (s || '').replace(/[\p{Extended_Pictographic}️‍]/gu, '').trim();

/** "2.B"/"5.A"/"SFO" i en titel → badge-tekst, ellers null. */
export function classBadge(title) {
  const m = (title || '').match(/\b(\d\.[A-ZÆØÅ]|SFO)\b/);
  return m ? m[1] : null;
}

const KIND_LABELS = {
  kommune: 'KOMMUNE', bank: 'BANK', forsikring: 'FORSIKRING',
  sundhed: 'SUNDHED', skole: 'SKOLE', forening: 'FORENING',
  butik: 'BUTIK', nyhedsbrev: 'LAV PRIORITET', andet: 'INFO',
};

/** Kategori-badge for et post-emne. Accent kun ved importance=high. */
export function postBadge(item) {
  return {
    label: KIND_LABELS[item.sender_kind] || 'INFO',
    tone: item.importance === 'high' ? 'accent' : 'neutral',
  };
}

/** Pending post-emner delt i handlingsliste og nyhedsbreve (til én række). */
export function partitionInbox(post) {
  const pending = (list) => (list || []).filter((i) => i.status === 'pending');
  const all = [...pending(post?.recent), ...pending(post?.info)];
  return {
    actionable: all.filter((i) => i.sender_kind !== 'nyhedsbrev'),
    newsletters: all.filter((i) => i.sender_kind === 'nyhedsbrev'),
  };
}

/** Primær pille: handling → godkend (opret opgave), info → kvittér. */
export function primaryAction(item) {
  if (item.intent === 'handling') {
    return { label: `Opret opgave: ${item.title}`, action: 'approve' };
  }
  return { label: 'Læs & kvittér', action: 'archive' };
}

/** Stille handling: handling → arkivér, info → senere (defer). */
export function quietAction(item) {
  if (item.intent === 'handling') return { label: 'Arkivér', action: 'archive' };
  return { label: 'Senere', action: 'defer' };
}

const WDS = ['søn', 'man', 'tir', 'ons', 'tor', 'fre', 'lør'];
const sameDay = (a, b) => a.toDateString() === b.toDateString();

/** Panelets frist-linje: "i dag inden 14:00" / "i morgen" / "ons 23.7." /
    "forfalden". null uden frist. */
export function dueLine(iso, now = new Date()) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isOverdue(iso) && !sameDay(d, now)) return 'forfalden';
  if (sameDay(d, now)) return `i dag inden ${fmtTime(iso)}`;
  if (sameDay(d, new Date(now.getTime() + 864e5))) return 'i morgen';
  return `${WDS[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
}

/** Tablet-heroens I DAG: maks 2 — først dagens næste tidsatte event (urgent),
    så mest presserende opgave, så pending Aula-handling. */
export function pickHighlights(doc, now = new Date()) {
  const out = [];
  const ev = (doc.events || []).find((e) => !e.all_day && e.start
    && sameDay(new Date(e.start), now) && new Date(e.start) > now);
  if (ev) out.push({ text: `${stripEmoji(ev.title)} kl. ${fmtTime(ev.start)}`, urgent: true });
  const task = (doc.tasks || []).find((t) => t.due
    && (isOverdue(t.due) || sameDay(new Date(t.due), now)));
  if (task && out.length < 2) {
    out.push({ text: stripEmoji(task.title), urgent: isOverdue(task.due) });
  }
  const aula = (doc.aula?.recent || []).find((i) => i.status === 'pending');
  if (aula && out.length < 2) out.push({ text: stripEmoji(aula.title), urgent: false });
  return out.slice(0, 2);
}

/** Nat-heroens I MORGEN-linje + morgendagens opgaver. */
export function tomorrowOverview(doc, now = new Date()) {
  const tomorrow = new Date(now.getTime() + 864e5);
  const ev = (doc.events || []).find((e) => e.start
    && sameDay(new Date(e.start), tomorrow));
  const wd = tomorrow.toLocaleDateString('da-DK', { weekday: 'long' });
  const cap = wd.charAt(0).toUpperCase() + wd.slice(1);
  const line = ev
    ? `${cap}: ${stripEmoji(ev.title)}${ev.all_day ? '' : ` kl. ${fmtTime(ev.start)}`}`
    : `${cap}: ingen aftaler`;
  const tasks = (doc.tasks || []).filter((t) => t.due
    && sameDay(new Date(t.due), tomorrow));
  return { line, tasks };
}

/** Wallpaperens DE NÆSTE DAGE: n dage frem med korte event-badges. */
export function nextDays(events, now = new Date(), n = 3) {
  return Array.from({ length: n }, (_, i) => {
    const day = new Date(now.getTime() + (i + 1) * 864e5);
    const badges = (events || [])
      .filter((e) => e.start && sameDay(new Date(e.start), day))
      .slice(0, 2)
      .map((e) => stripEmoji(e.title).split('—')[0].trim());
    return {
      weekday: day.toLocaleDateString('da-DK', { weekday: 'long' }),
      badges,
    };
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd dashboard && npm test`
Expected: all tests PASS (2 files).

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/paper/paperLogic.js dashboard/src/components/paper/paperNight.js dashboard/test dashboard/package.json
git commit -m "Warm Paper: ren logik (badges, inbox-partition, highlights, nat) + node --test"
```

---

### Task 7: Data plumbing — `usePaperData`, api.js actions, mock extensions

**Files:**
- Create: `dashboard/src/components/paper/usePaperData.js`
- Modify: `dashboard/src/lib/api.js` (three new functions)
- Modify: `dashboard/src/lib/mock.js` (shopping block + mockPanelStatus)

**Interfaces:**
- Consumes: `fetchDashboard(ambient)` from `api.js` (existing), Task 1's `shopping` shape, Task 4's `/api/panel/status` shape.
- Produces:
  - `usePaperData(ambient) -> {doc, error, now}` — polls every 120 s (data) / 15 s (clock), mirrors `Dashboard.jsx` cadence; keeps last good doc on failure and sets `error` true.
  - `fetchPanelStatus() -> Promise<{generated_at, services}>` — also returns `latency_ms` measured client-side.
  - `postTriageAction(id, action) -> Promise<{ok, receipt}>` (throws on !ok).
  - `archiveNewsletters() -> Promise<{ok, archived}>`.
  - `mockDocument(false)` now includes `shopping`; new export `mockPanelStatus()`.

- [ ] **Step 1: Extend `api.js`**

Append to `dashboard/src/lib/api.js`:

```js
/** DRIFT-footer til /paper/panel. Måler selv svartiden (brain-rækken). */
export async function fetchPanelStatus() {
  const t0 = performance.now();
  try {
    const res = await fetch(`${BASE}/api/panel/status`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const doc = await res.json();
    return { ...doc, latency_ms: Math.round(performance.now() - t0) };
  } catch (err) {
    if (import.meta.env.DEV) {
      const { mockPanelStatus } = await import('./mock.js');
      return mockPanelStatus();
    }
    throw err;
  }
}

/** Panel-pille: godkend/arkivér/udsæt et post-emne. Kaster ved fejl. */
export async function postTriageAction(id, action) {
  const res = await fetch(`${BASE}/api/post/${id}/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** Panel: arkivér alle pending nyhedsbreve. Kaster ved fejl. */
export async function archiveNewsletters() {
  const res = await fetch(`${BASE}/api/post/archive-newsletters`, { method: 'POST' });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Extend `mock.js`**

In `mockDocument`, inside the `if (!ambient) {` block (next to `doc.post`), add:

```js
    // Warm Paper tablet: indkøbs-pills (åbne tasks i Vikunja-indkøbsprojektet).
    doc.shopping = {
      stale: false,
      items: [
        { id: 41, title: 'Mælk' }, { id: 42, title: 'Rugbrød' },
        { id: 43, title: 'Æg' }, { id: 44, title: 'Bananer' },
        { id: 45, title: 'Kaffe' }, { id: 46, title: 'Fødselsdagsgave 🎁' },
      ],
    };
```

Also add `id` + `deferred_until` to the existing `doc.post` mock rows (feed rows carry them after Task 2) — e.g. `{ id: 21, title: 'Årsopgørelse klar i TastSelv', ..., deferred_until: null }`, ids 21–23. Add one newsletter row to `post.info` so the panel's collapsed row renders in dev:

```js
        { id: 24, title: 'Ugens tilbud fra Nemlig', summary: 'Nyhedsbrev.', created_at: at(0, 6, 0), status: 'pending', importance: 'low', sender_kind: 'nyhedsbrev', deferred_until: null },
```

And append the new export at the end of the file:

```js
/* Mock til /paper/panel's DRIFT-footer — formen matcher panel_status.build(). */
export function mockPanelStatus() {
  return {
    generated_at: new Date().toISOString(),
    latency_ms: 42,
    services: [
      { name: 'vikunja', state: 'ok', detail: 'sync 14:28' },
      { name: 'kalender', state: 'ok', detail: 'sync 14:30' },
      { name: 'vejr', state: 'ok', detail: 'sync 14:00' },
      { name: 'madplan', state: 'ok', detail: 'sync 13:45' },
      { name: 'gmail-triage', state: 'ok', detail: 'seneste 14:25' },
      { name: 'aula', state: 'warn', detail: 'seneste 09:12' },
      { name: 'ollama', state: 'ok', detail: 'qwen2.5:7b-instruct' },
    ],
  };
}
```

- [ ] **Step 3: Write `usePaperData.js`**

```js
/* Delt poll-hook for alle tre paper-flader. Samme kadence som space-temaets
   Dashboard.jsx: data hvert 120 s, klokke hvert 15 s. Ved fetch-fejl beholdes
   sidste gode dokument og error sættes — fladerne viser en stille mono-linje. */
import { useEffect, useState } from 'react';
import { fetchDashboard } from '../../lib/api.js';

export function usePaperData(ambient = false) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    let alive = true;
    const load = () => fetchDashboard(ambient)
      .then((d) => { if (alive) { setDoc(d); setError(false); } })
      .catch(() => { if (alive) setError(true); });
    load();
    const dataId = setInterval(load, 120_000);
    const clockId = setInterval(() => setNow(new Date()), 15_000);
    return () => { alive = false; clearInterval(dataId); clearInterval(clockId); };
  }, [ambient]);

  return { doc, error, now };
}
```

- [ ] **Step 4: Verify tests and build**

Run: `cd dashboard && npm test && npm run build`
Expected: tests PASS, build clean.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/lib/api.js dashboard/src/lib/mock.js dashboard/src/components/paper/usePaperData.js
git commit -m "Warm Paper: usePaperData-hook, panel-API-kald og mock-udvidelser"
```

---

### Task 8: `/paper/tablet` (mockups 1d + 1e)

**Files:**
- Create: `dashboard/src/components/paper/PaperTablet.jsx`
- Create: `dashboard/src/pages/paper/tablet.astro`

**Interfaces:**
- Consumes: `usePaperData(false)`, `isNight`, `pickHighlights`, `tomorrowOverview`, `classBadge`, `stripEmoji`, `dueLine` (Tasks 6–7); `fmtClock`, `fmtTime`, `weatherLabel` from `lib/format.js`; tokens/classes from `paper.css`.
- Produces: route `/paper/tablet`. Read-only; no click handlers.

- [ ] **Step 1: Write `tablet.astro`**

```astro
---
import Base from '../../layouts/Base.astro';
import PaperTablet from '../../components/paper/PaperTablet.jsx';
import '../../styles/paper.css';
---
<Base title="LifeHub — papir">
  <PaperTablet client:load />
</Base>
```

- [ ] **Step 2: Write `PaperTablet.jsx`**

Layout constants come straight from mockup 1d (sizes are px at 2560×1600; the surface is a fixed kiosk so fixed px is correct — same approach as the mockup). Full component:

```jsx
/* Warm Paper familie-dashboard (mockup 1d dag / 1e nat). Ren visning —
   ingen handlinger. Nat efter solnedgang: I MORGEN i stedet for I DAG. */
import { usePaperData } from './usePaperData.js';
import { isNight } from './paperNight.js';
import { pickHighlights, tomorrowOverview, classBadge, stripEmoji, dueLine } from './paperLogic.js';
import { fmtClock, weatherLabel } from '../../lib/format.js';

const Label = ({ children, accent, right }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
    <div className="paper-mono" style={{ fontSize: 24, color: accent ? 'var(--accent)' : 'var(--muted)' }}>
      {children}
    </div>
    {right != null && <div className="paper-mono" style={{ fontSize: 24, color: 'var(--faint)' }}>{right}</div>}
  </div>
);

function TaskRow({ task, now, last }) {
  const due = task.due && dueLine(task.due, now);
  const urgent = due && due.startsWith('i dag');
  return (
    <div style={{ display: 'flex', gap: 26, alignItems: 'center', padding: '22px 0',
                  borderBottom: last ? 'none' : '1px solid var(--hairline)' }}>
      <div className="paper-dot" style={{ width: 30, height: 30,
        border: `3px solid ${urgent ? 'var(--accent)' : 'var(--circle-idle)'}` }} />
      <div style={{ fontSize: 36, fontWeight: 500 }}>{stripEmoji(task.title)}</div>
      {urgent && <div className="paper-mono" style={{ fontSize: 22, color: 'var(--accent)', marginLeft: 'auto' }}>
        inden {task.due.slice(11, 16)}
      </div>}
    </div>
  );
}

function DoneRow({ task }) {
  return (
    <div style={{ display: 'flex', gap: 26, alignItems: 'center', padding: '22px 0' }}>
      <div className="paper-dot" style={{ width: 30, height: 30, background: 'var(--done-fill)',
        color: 'var(--paper-bg)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 20, fontWeight: 700 }}>✓</div>
      <div style={{ fontSize: 36, fontWeight: 500, color: 'var(--faint)',
                    textDecoration: 'line-through' }}>{stripEmoji(task.title)}</div>
    </div>
  );
}

export default function PaperTablet() {
  const { doc, error, now } = usePaperData(false);
  if (!doc) return <div className="paper-root" />;

  const night = isNight(now, doc.weather);
  const w = doc.weather;
  const dateLine = now.toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });
  const weatherLine = w
    ? `${weatherLabel(w.code).charAt(0).toUpperCase() + weatherLabel(w.code).slice(1)}` +
      (night && w.sunrise ? ` — solopgang kl. ${w.sunrise.slice(11, 16).replace(':', '.')}` : '')
    : '';

  const highlights = night ? null : pickHighlights(doc, now);
  const tomorrow = night ? tomorrowOverview(doc, now) : null;
  const tasks = night ? tomorrow.tasks : (doc.tasks || []).slice(0, 4);
  const lastDone = !night && (doc.tasks_done || [])[0];
  const shopping = (doc.shopping?.items || []).slice(0, 8);
  const aulaRows = [...(doc.aula?.info || []), ...(doc.aula?.recent || [])].slice(0, 3);

  return (
    <div className="paper-root" data-mode={night ? 'night' : 'day'}
         style={{ padding: '110px 120px', display: 'grid',
                  gridTemplateColumns: '1.05fr 1fr', gap: 140 }}>
      {/* — venstre: hero — */}
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div className="paper-clock" style={{ fontSize: 400, fontWeight: 600,
             letterSpacing: '-0.045em', lineHeight: 0.95 }}>{fmtClock(now)}</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 40, marginTop: 52 }}>
          <div style={{ fontSize: 62, fontWeight: 600, letterSpacing: '-0.015em',
                        color: night ? 'var(--ink-2)' : 'var(--ink)' }}>{dateLine}</div>
          {w && <div style={{ fontSize: 62, fontWeight: 400, color: 'var(--muted)' }}>
            {Math.round(w.now_c)}°</div>}
        </div>
        <div style={{ fontSize: 38, color: 'var(--muted)', marginTop: 14 }}>
          {error ? `opdateret ${doc.generated_at?.slice(11, 16)} · offline` : weatherLine}
        </div>
        <div style={{ marginTop: 'auto' }}>
          <div className="paper-mono" style={{ fontSize: 24, color: 'var(--accent)' }}>
            {night ? 'I MORGEN' : 'I DAG'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 36, marginTop: 32 }}>
            {night ? (
              <div style={{ display: 'flex', gap: 30, alignItems: 'baseline' }}>
                <div className="paper-dot" style={{ width: 16, height: 16,
                  border: '3px solid var(--accent)', transform: 'translateY(-6px)' }} />
                <div style={{ fontSize: 56, fontWeight: 600, lineHeight: 1.2,
                              color: 'var(--ink-2)' }}>{tomorrow.line}</div>
              </div>
            ) : highlights.map((h, i) => (
              <div key={i} style={{ display: 'flex', gap: 30, alignItems: 'baseline' }}>
                <div className="paper-dot" style={{ width: 16, height: 16, flex: 'none',
                  transform: 'translateY(-6px)',
                  ...(h.urgent ? { background: 'var(--accent)' }
                              : { border: '3px solid var(--accent)' }) }} />
                <div style={{ fontSize: 56, fontWeight: 600, lineHeight: 1.2,
                              letterSpacing: '-0.01em',
                              color: i === 0 ? 'var(--ink)' : 'var(--ink-2)' }}>{h.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {/* — højre kolonne bag hairline — */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 70,
                    borderLeft: '1px solid var(--hairline-strong)', paddingLeft: 110,
                    opacity: 'var(--side-opacity)' }}>
        <div>
          <Label right={tasks.length}>{night ? 'OPGAVER I MORGEN' : 'OPGAVER'}</Label>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 20 }}>
            {tasks.map((t, i) => (
              <TaskRow key={t.id} task={t} now={now}
                       last={i === tasks.length - 1 && !lastDone} />
            ))}
            {lastDone && <DoneRow task={lastDone} />}
          </div>
        </div>
        {!night && shopping.length > 0 && (
          <div>
            <Label>INDKØB</Label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px 18px', marginTop: 24 }}>
              {shopping.map((s) => (
                <div key={s.id} className="paper-pill" style={{ fontSize: 32, padding: '12px 26px' }}>
                  {stripEmoji(s.title)}
                </div>
              ))}
            </div>
          </div>
        )}
        <div>
          <Label>SKOLE</Label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 30, marginTop: 24 }}>
            {aulaRows.map((a, i) => {
              const badge = classBadge(a.title);
              return (
                <div key={i} style={{ display: 'flex', gap: 24, alignItems: 'baseline' }}>
                  <div className={`paper-badge${badge ? '' : ' paper-badge--neutral'}`}
                       style={{ fontSize: 24, flex: 'none' }}>{badge || 'AULA'}</div>
                  <div style={{ fontSize: 34, lineHeight: 1.35,
                                color: night ? 'var(--ink-2)' : 'var(--ink)' }}>
                    {stripEmoji(a.title)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build + visual check**

Run: `cd dashboard && npm test && npm run build`
Expected: PASS + clean build.

Then `npm run dev`, open `http://localhost:4321/paper/tablet` in Chrome with DevTools device emulation at **2560×1600**. Compare against mockup 1d: hero clock dominates left, I DAG max 2 items, right column hairline with OPGAVER/INDKØB/SKOLE. Force night: temporarily change `data-mode={night ? ...}` check via DevTools (edit attribute to `night`) and compare against 1e. Screenshot both.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/pages/paper/tablet.astro dashboard/src/components/paper/PaperTablet.jsx
git commit -m "Warm Paper: /paper/tablet — familiedashboard med dag/nat (mockup 1d/1e)"
```

---

### Task 9: `/paper/wallpaper` (mockup 1f)

**Files:**
- Create: `dashboard/src/components/paper/PaperWallpaper.jsx`
- Create: `dashboard/src/pages/paper/wallpaper.astro`

**Interfaces:**
- Consumes: `usePaperData(true)` (ambient doc — never `post`/`finance`), `nextDays`, `stripEmoji`, `pickHighlights` (Task 6), `isoWeek`, `weatherLabel`, `fmtClock` from `lib/format.js`; keyframes from `paper.css`.
- Produces: route `/paper/wallpaper`. `?drift=<seconds>` overrides `--drift-base` (default 320s; demo: `?drift=70`).

- [ ] **Step 1: Write `wallpaper.astro`**

```astro
---
import Base from '../../layouts/Base.astro';
import PaperWallpaper from '../../components/paper/PaperWallpaper.jsx';
import '../../styles/paper.css';
---
<Base title="LifeHub — papir wallpaper">
  <PaperWallpaper client:load />
</Base>
```

- [ ] **Step 2: Write `PaperWallpaper.jsx`**

```jsx
/* Warm Paper ultrawide-wallpaper (mockup 1f, 5120×1440). Center ≥2900px er
   TOMT — vinduer bor der. Intet handlingsbart, intet der haster.
   Drift-hastighed: ?drift=<sekunder> (produktionsdefault 320s; demo ~70s). */
import { usePaperData } from './usePaperData.js';
import { nextDays, stripEmoji, pickHighlights } from './paperLogic.js';
import { isoWeek, weatherLabel } from '../../lib/format.js';

const PATCHES = [
  { left: -400, top: 90, w: 1500, h: 420, color: 'rgba(255,253,246,1)', blur: 40, anim: 'lh-drift-a', mult: 1, delay: '0s' },
  { left: -600, top: 640, w: 1100, h: 340, color: 'rgba(185,92,56,.14)', blur: 50, anim: 'lh-drift-a', mult: 1.3, delay: '-40s' },
  { left: 0, top: 340, w: 1300, h: 380, color: 'rgba(255,253,246,.95)', blur: 45, anim: 'lh-drift-b', mult: 1.15, delay: '-25s' },
  { left: -300, top: 1080, w: 900, h: 300, color: 'rgba(222,207,178,.8)', blur: 38, anim: 'lh-drift-a', mult: 1.5, delay: '-70s' },
];

export default function PaperWallpaper() {
  const { doc, now } = usePaperData(true);
  const drift = Number(new URLSearchParams(window.location.search).get('drift')) || 320;
  if (!doc) return <div className="paper-root" style={{ '--paper-bg': '#f1ede4' }} />;

  const w = doc.weather;
  const days = nextDays(doc.events, now, 3);
  const note = pickHighlights(doc, now)[0];
  const weekday = now.toLocaleDateString('da-DK', { weekday: 'long' }).toUpperCase();
  const month = now.toLocaleDateString('da-DK', { month: 'long' });

  return (
    <div className="paper-root" style={{ '--paper-bg': '#f1ede4', position: 'relative' }}>
      {/* — drivende lyspletter (hele bredden; produktion ≥300 s pr. tur) — */}
      {PATCHES.map((p, i) => (
        <div key={i} className="paper-drift" style={{ position: 'absolute',
          left: p.left, top: p.top, width: p.w, height: p.h,
          background: `radial-gradient(closest-side, ${p.color}, transparent)`,
          filter: `blur(${p.blur}px)`,
          animation: `${p.anim} ${Math.round(drift * p.mult)}s linear infinite`,
          animationDelay: p.delay }} />
      ))}
      {/* — venstre vinge — */}
      <div className="paper-sway" style={{ position: 'absolute', left: 150, top: 130,
           bottom: 130, width: 900, display: 'flex', flexDirection: 'column', zIndex: 1,
           animation: 'lh-sway var(--sway-a) ease-in-out infinite' }}>
        <div className="paper-mono" style={{ fontSize: 30, letterSpacing: '.18em',
             color: 'var(--muted)' }}>{weekday} · UGE {isoWeek(now)}</div>
        <div className="paper-clock" style={{ fontSize: 560, fontWeight: 600,
             letterSpacing: '-0.05em', lineHeight: 0.9, marginTop: 20 }}>{now.getDate()}</div>
        <div style={{ fontSize: 76, fontWeight: 600, letterSpacing: '-0.01em', marginTop: 24 }}>
          {month} <span style={{ color: 'var(--muted)', fontWeight: 400 }}>{now.getFullYear()}</span>
        </div>
        {w && (
          <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'baseline', gap: 44 }}>
            <div style={{ fontSize: 150, fontWeight: 500, letterSpacing: '-0.03em' }}>
              {Math.round(w.now_c)}°</div>
            <div>
              <div style={{ fontSize: 44, color: 'var(--ink-2)' }}>
                {weatherLabel(w.code).charAt(0).toUpperCase() + weatherLabel(w.code).slice(1)}
              </div>
              <div className="paper-mono" style={{ fontSize: 30, color: 'var(--muted)', marginTop: 10 }}>
                ↑ {w.sunrise?.slice(11, 16)}&nbsp;&nbsp;↓ {w.sunset?.slice(11, 16)}
              </div>
            </div>
          </div>
        )}
      </div>
      {/* — højre vinge — */}
      <div className="paper-sway" style={{ position: 'absolute', right: 150, top: 130,
           bottom: 130, width: 820, display: 'flex', flexDirection: 'column',
           alignItems: 'flex-end', textAlign: 'right', zIndex: 1,
           animation: 'lh-sway var(--sway-b) ease-in-out infinite', animationDelay: '-55s' }}>
        <div className="paper-mono" style={{ fontSize: 30, letterSpacing: '.18em',
             color: 'var(--muted)' }}>DE NÆSTE DAGE</div>
        <div style={{ display: 'flex', flexDirection: 'column', marginTop: 34, width: '100%' }}>
          {days.map((d, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                 alignItems: 'baseline', padding: '30px 0',
                 borderBottom: i < days.length - 1 ? '1px solid var(--hairline-strong)' : 'none' }}>
              <div style={{ fontSize: 44, fontWeight: 600 }}>
                {d.weekday}
                {d.badges.map((b, j) => (
                  <span key={j} className="paper-badge" style={{ fontSize: 28,
                        fontWeight: 400, marginLeft: 14 }}>{b}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
        {note && (
          <div style={{ marginTop: 'auto', fontSize: 44, color: 'var(--ink-2)', lineHeight: 1.4 }}>
            I dag: {note.text} <span className="paper-breathe" style={{ color: 'var(--accent)',
              display: 'inline-block', animation: 'lh-breathe 7s ease-in-out infinite' }}>●</span>
          </div>
        )}
      </div>
      <div className="paper-mono" style={{ position: 'absolute', left: '50%', bottom: 70,
           transform: 'translateX(-50%)', fontSize: 26, letterSpacing: '.3em',
           color: 'var(--hairline-strong)' }}>· · ·</div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build + visual check**

Run: `cd dashboard && npm run build`
Expected: clean.

Dev check at **5120×1440** emulation on `/paper/wallpaper?drift=70` (demo speed): wings only, center empty (≥2900px between wing inner edges: 5120 − 150 − 900 − 150 − 820 = 3100px ✓), patches drifting, sway visible over ~1 min. Then check `/paper/wallpaper` (no param) — motion barely perceptible (320s). Emulate `prefers-reduced-motion: reduce` in DevTools rendering tab → all motion stops. Screenshot.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/pages/paper/wallpaper.astro dashboard/src/components/paper/PaperWallpaper.jsx
git commit -m "Warm Paper: /paper/wallpaper — ultrawide ambient-lag med rolig drift (mockup 1f)"
```

---

### Task 10: `/paper/panel` (mockup 1g)

**Files:**
- Create: `dashboard/src/components/paper/PaperPanel.jsx`
- Create: `dashboard/src/pages/paper/panel.astro`

**Interfaces:**
- Consumes: `usePaperData(false)` (admin doc → `post` when viewer is admin), `fetchPanelStatus`, `postTriageAction`, `archiveNewsletters` (Task 7), `partitionInbox`, `postBadge`, `primaryAction`, `quietAction`, `dueLine`, `classBadge`, `stripEmoji` (Task 6), `fmtClock` from `lib/format.js`.
- Produces: route `/paper/panel`. The only interactive paper surface.

- [ ] **Step 1: Write `panel.astro`**

```astro
---
import Base from '../../layouts/Base.astro';
import PaperPanel from '../../components/paper/PaperPanel.jsx';
import '../../styles/paper.css';
---
<Base title="LifeHub — handlingspanel">
  <PaperPanel client:load />
</Base>
```

- [ ] **Step 2: Write `PaperPanel.jsx`**

```jsx
/* Warm Paper handlingspanel (mockup 1g, 1920×1080). Eneste interaktive
   paper-flade: indbakke-piller kalder brain-endpoints optimistisk — rækken
   fader ud med det samme og genindsættes med en stille notits ved fejl. */
import { useEffect, useState } from 'react';
import { usePaperData } from './usePaperData.js';
import { fetchPanelStatus, postTriageAction, archiveNewsletters } from '../../lib/api.js';
import { partitionInbox, postBadge, primaryAction, quietAction, dueLine,
         classBadge, stripEmoji } from './paperLogic.js';
import { fmtClock } from '../../lib/format.js';

const SectionLabel = ({ children, right }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
    <div className="paper-mono" style={{ fontSize: 14, color: 'var(--muted)' }}>{children}</div>
    {right != null && <div className="paper-mono" style={{ fontSize: 14, color: 'var(--faint)' }}>{right}</div>}
  </div>
);

function InboxRow({ item, onAction, failed }) {
  const badge = postBadge(item);
  const prim = primaryAction(item);
  const quiet = quietAction(item);
  return (
    <div style={{ padding: '18px 0', borderBottom: '1px solid var(--hairline)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: 18, fontWeight: 700 }}>{stripEmoji(item.title)}</div>
        <div className={`paper-badge${badge.tone === 'neutral' ? ' paper-badge--neutral' : ''}`}
             style={{ fontSize: 12 }}>{badge.label}</div>
      </div>
      {item.summary && <div style={{ fontSize: 17, color: 'var(--ink-2)', marginTop: 4 }}>
        {stripEmoji(item.summary)}</div>}
      <div style={{ display: 'flex', gap: 12, marginTop: 12, alignItems: 'center' }}>
        <button onClick={() => onAction(item, prim.action)} className="paper-pill"
                style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent)',
                         borderColor: 'var(--accent)', padding: '6px 18px',
                         background: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
          {prim.label}
        </button>
        <button onClick={() => onAction(item, quiet.action)}
                style={{ fontSize: 15, fontWeight: 500, color: 'var(--muted)', padding: '6px 12px',
                         background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
          {quiet.label}
        </button>
        {failed && <div className="paper-mono" style={{ fontSize: 12, color: 'var(--warn)' }}>
          kunne ikke gennemføres</div>}
      </div>
    </div>
  );
}

export default function PaperPanel() {
  const { doc, error, now } = usePaperData(false);
  const [status, setStatus] = useState(null);
  const [hidden, setHidden] = useState(new Set());   // optimistisk skjulte ids
  const [failed, setFailed] = useState(new Set());   // ids med fejlet handling

  useEffect(() => {
    let alive = true;
    const load = () => fetchPanelStatus()
      .then((s) => { if (alive) setStatus(s); })
      .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!doc) return <div className="paper-root" />;

  const act = (item, action) => {
    setHidden((h) => new Set(h).add(item.id));
    setFailed((f) => { const n = new Set(f); n.delete(item.id); return n; });
    postTriageAction(item.id, action).catch(() => {
      setHidden((h) => { const n = new Set(h); n.delete(item.id); return n; });
      setFailed((f) => new Set(f).add(item.id));
    });
  };
  const actNewsletters = (ids) => {
    setHidden((h) => new Set([...h, ...ids]));
    archiveNewsletters().catch(() => {
      setHidden((h) => { const n = new Set(h); ids.forEach((i) => n.delete(i)); return n; });
    });
  };

  const { actionable, newsletters } = partitionInbox(doc.post);
  const inbox = actionable.filter((i) => !hidden.has(i.id));
  const letters = newsletters.filter((i) => !hidden.has(i.id));
  const withDue = (doc.tasks || []).filter((t) => t.due);
  const noDue = (doc.tasks || []).filter((t) => !t.due);
  const aulaRows = [...(doc.aula?.recent || []), ...(doc.aula?.info || [])].slice(0, 3);
  const dateLine = now.toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="paper-root" style={{ padding: '56px 64px', display: 'flex',
                                         flexDirection: 'column', fontSize: 16 }}>
      {/* — header med tung 2px-linje — */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                    paddingBottom: 26, borderBottom: '2px solid var(--ink)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 18 }}>
          <div style={{ fontSize: 26, fontWeight: 700 }}>LifeHub</div>
          <div className="paper-mono" style={{ fontSize: 14, letterSpacing: '.14em',
               color: 'var(--muted)' }}>HANDLINGSPANEL</div>
          {error && <div className="paper-mono" style={{ fontSize: 13, color: 'var(--faint)' }}>
            opdateret {doc.generated_at?.slice(11, 16)} · offline</div>}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 22 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{dateLine}</div>
          <div className="paper-mono paper-clock" style={{ fontSize: 20, fontWeight: 500 }}>
            {fmtClock(now)}</div>
        </div>
      </div>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '460px 1fr 430px',
                    gap: 56, paddingTop: 36, minHeight: 0 }}>
        {/* — kolonne 1: opgaver — */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <SectionLabel right={`${(doc.tasks || []).length} · Vikunja`}>OPGAVER</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10 }}>
            {withDue.slice(0, 5).map((t) => {
              const due = dueLine(t.due, now);
              const urgent = due && (due.startsWith('i dag') || due === 'forfalden');
              return (
                <div key={t.id} style={{ display: 'flex', gap: 16, alignItems: 'baseline',
                     padding: '16px 0', borderBottom: '1px solid var(--hairline)' }}>
                  <div className="paper-dot" style={{ width: 18, height: 18,
                    border: `2px solid ${urgent ? 'var(--accent)' : 'var(--circle-idle)'}`,
                    transform: 'translateY(3px)' }} />
                  <div>
                    <div style={{ fontSize: 19, fontWeight: urgent ? 600 : 500 }}>
                      {stripEmoji(t.title)}</div>
                    <div className="paper-mono" style={{ fontSize: 13, marginTop: 3,
                         color: urgent ? 'var(--accent)' : 'var(--muted)',
                         textTransform: 'none', letterSpacing: 0 }}>{due}</div>
                  </div>
                </div>
              );
            })}
          </div>
          {noDue.length > 0 && (
            <div className="paper-mono" style={{ marginTop: 'auto', fontSize: 13,
                 color: 'var(--faint)', textTransform: 'none', letterSpacing: 0 }}>
              + {noDue.length} uden frist</div>
          )}
        </div>
        {/* — kolonne 2: indbakke-triage — */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0,
                      borderLeft: '1px solid var(--hairline-strong)',
                      borderRight: '1px solid var(--hairline-strong)', padding: '0 56px' }}>
          <SectionLabel right={doc.post ? `${doc.post.new_today} nye` : null}>
            INDBAKKE · TIL GENNEMSYN</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10, overflow: 'hidden' }}>
            {!doc.post && (
              <div style={{ fontSize: 17, color: 'var(--faint)', paddingTop: 18 }}>
                Ingen adgang til indbakken fra denne enhed.</div>
            )}
            {inbox.slice(0, 4).map((item) => (
              <InboxRow key={item.id} item={item} onAction={act} failed={failed.has(item.id)} />
            ))}
            {letters.length > 0 && (
              <div style={{ padding: '18px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--muted)' }}>
                    {letters.length} nyhedsbrev{letters.length === 1 ? '' : 'e'}</div>
                  <div className="paper-badge paper-badge--neutral" style={{ fontSize: 12 }}>
                    LAV PRIORITET</div>
                </div>
                <div style={{ marginTop: 12 }}>
                  <button onClick={() => actNewsletters(letters.map((l) => l.id))}
                          className="paper-pill"
                          style={{ fontSize: 15, fontWeight: 600, color: 'var(--muted)',
                                   padding: '6px 18px', background: 'none', cursor: 'pointer',
                                   fontFamily: 'inherit' }}>
                    Arkivér alle
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
        {/* — kolonne 3: skole/aula + DRIFT — */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <SectionLabel>SKOLE / AULA</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10 }}>
            {aulaRows.map((a, i) => {
              const badge = classBadge(a.title);
              return (
                <div key={i} style={{ padding: '16px 0', borderBottom: '1px solid var(--hairline)' }}>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                    <div className={`paper-badge${badge ? '' : ' paper-badge--neutral'}`}
                         style={{ fontSize: 13, flex: 'none' }}>{badge || 'AULA'}</div>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{stripEmoji(a.title)}</div>
                    {a.date && <div className="paper-mono" style={{ fontSize: 13,
                         color: 'var(--muted)', marginLeft: 'auto', textTransform: 'none',
                         letterSpacing: 0 }}>{a.date.slice(8, 10)}.{Number(a.date.slice(5, 7))}
                         {a.time ? ` · ${a.time.slice(0, 5)}` : ''}</div>}
                  </div>
                  {a.summary && <div style={{ fontSize: 16, color: 'var(--ink-2)', marginTop: 6,
                       lineHeight: 1.45 }}>{stripEmoji(a.summary)}</div>}
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 'auto' }}>
            <div className="paper-mono" style={{ fontSize: 14, color: 'var(--muted)',
                 paddingTop: 20, borderTop: '1px solid var(--hairline-strong)' }}>DRIFT</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14,
                          fontFamily: 'var(--font-mono)', fontSize: 14 }}>
              {status && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="paper-dot" style={{ width: 9, height: 9, background: 'var(--ok)' }} />
                  <div>brain (FastAPI)</div>
                  <div style={{ color: 'var(--faint)', marginLeft: 'auto' }}>{status.latency_ms} ms</div>
                </div>
              )}
              {(status?.services || []).map((s) => (
                <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10,
                     opacity: s.state === 'off' ? 0.45 : 1 }}>
                  <div className="paper-dot" style={{ width: 9, height: 9,
                    background: s.state === 'warn' ? 'var(--warn)' : 'var(--ok)' }} />
                  <div>{s.name}</div>
                  <div style={{ color: 'var(--faint)', marginLeft: 'auto' }}>{s.detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build + visual + interaction check**

Run: `cd dashboard && npm test && npm run build`
Expected: PASS + clean.

Dev check at **1920×1080** on `/paper/panel` (mock data): three columns with hairlines, header rule 2px, inbox rows with one accent pill + one quiet action, newsletters collapsed with "Arkivér alle", DRIFT footer with dots. Click a pill: row disappears immediately (optimistic); the mock POST fails in dev without brain → row returns with "kunne ikke gennemføres". That failure-path check **is** the interaction test.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/pages/paper/panel.astro dashboard/src/components/paper/PaperPanel.jsx
git commit -m "Warm Paper: /paper/panel — handlingspanel med triage-piller og DRIFT (mockup 1g)"
```

---

### Task 11: End-to-end verification

**Files:** none created — verification only (fix regressions where found).

- [ ] **Step 1: Full test suites**

Run: `cd brain && python -m pytest tests/ -v` → all PASS.
Run: `cd dashboard && npm test && npm run build` → all PASS, clean build.

- [ ] **Step 2: Backend smoke test against dev brain**

Start brain locally (or against the running instance). With an admin `Cf-Access-Authenticated-User-Email` header:

```bash
curl -s http://localhost:8000/api/panel/status -H "Cf-Access-Authenticated-User-Email: mba@nova-tech.dk" | python -m json.tool
curl -s -X POST http://localhost:8000/api/post/1/action -H "Cf-Access-Authenticated-User-Email: mba@nova-tech.dk" -H "Content-Type: application/json" -d '{"action":"defer"}'
curl -s -X POST http://localhost:8000/api/post/archive-newsletters -H "Cf-Access-Authenticated-User-Email: mba@nova-tech.dk"
curl -s http://localhost:8000/api/dashboard | python -c "import json,sys; d=json.load(sys.stdin); print('shopping' in d)"
```

Expected: status JSON with `services`; action returns `{"ok": true}` or 404 if item 1 doesn't exist (both acceptable — the gate and routing work); newsletters returns `{"ok": true, "archived": N}`; dashboard prints `True` (after `refresh_shopping` has run once). Without the header everything mutating returns 403 — verify one:

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/post/1/action -d '{"action":"defer"}'
```

Expected: `403`.

- [ ] **Step 3: Visual pass on all three routes**

Dev server + Chrome device emulation. Screenshot each and compare to mockups:
- `/paper/tablet` @2560×1600 vs 1d; force `data-mode="night"` vs 1e.
- `/paper/wallpaper?drift=70` @5120×1440 vs 1f; verify empty center and reduced-motion emulation stops everything.
- `/paper/panel` @1920×1080 vs 1g.

Also open `/` and `/ambient` and verify the space theme is pixel-identical to before (no paper.css leakage, no font changes).

- [ ] **Step 4: Final commit (if fixes were made) and wrap-up**

```bash
git status
git add -A && git commit -m "Warm Paper: e2e-verifikation og finpudsning"
```

Then follow the superpowers:finishing-a-development-branch skill.

"""Strong-model quality pass over the review queue (Pass 2 of dual-pass parsing).

Driven by the GPU boot agent calling POST /api/review/drain. Each pending item
goes through the relevance model:
  1. Hard age cap (REVIEW_HARD_MAX_AGE_DAYS) -> expired, no re-parse.
  2. Action gone, task done, or event already over -> expired.
  3. Live state no longer matches pass1_parsed -> the user edited it by hand;
     a human's change is never overwritten -> mark done, skip.
  4. Re-parse with the strong model, anchored at the message's ORIGINAL
     received_at (never the current time). Differences on significant fields
     are applied to the created action; one summary Telegram message per chat.

Empty STRONG_OLLAMA_URL disables everything.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil import parser as dtparse

from . import config, gcal, llm, store, telegram, vikunja

log = logging.getLogger(__name__)

#: Fields that constitute a "different interpretation" (spec: betydende felter).
_LABELS = {"intent": "type", "title": "titel", "start": "start", "end": "slut",
           "due": "frist", "all_day": "heldag", "amount_dkk": "beløb", "items": "varer"}


def _tz() -> ZoneInfo:
    return ZoneInfo(config.TZ)


def _norm_dt(value: str | None, date_only: bool = False) -> str | None:
    """Normalise any date/datetime string to Europe/Copenhagen for comparison."""
    if not value:
        return None
    try:
        dt = dtparse.parse(value)
    except (ValueError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    dt = dt.astimezone(_tz())
    return dt.date().isoformat() if date_only else dt.isoformat(timespec="minutes")


def _norm_title(value: str | None) -> str:
    return (value or "").strip().casefold()


def _fingerprint(parsed: dict) -> dict:
    all_day = bool(parsed.get("all_day"))
    return {
        "intent": parsed.get("intent"),
        "title": _norm_title(parsed.get("title")),
        "start": _norm_dt(parsed.get("start"), date_only=all_day),
        "end": _norm_dt(parsed.get("end") or parsed.get("start"), date_only=all_day),
        "due": _norm_dt(parsed.get("due"), date_only=True),
        "all_day": all_day,
        "amount_dkk": round(float(parsed.get("amount_dkk") or 0), 2),
        "items": sorted(_norm_title(i) for i in (parsed.get("items") or [])),
    }


def _fmt(value) -> str:
    if value is None or value == [] or value == "":
        return "–"
    if isinstance(value, list):
        return ", ".join(value)
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, str):
        return value.replace("T", " kl. ") if "T" in value else value
    return str(value)


def _diff_desc(old_fp: dict, new_fp: dict) -> str:
    return ", ".join(f"{label}: {_fmt(old_fp[key])} → {_fmt(new_fp[key])}"
                     for key, label in _LABELS.items() if old_fp[key] != new_fp[key])


# ── Human-wins checks: live state vs pass1_parsed, per kind ────────
# Deliberately fail-safe: any doubt reads as "the user touched this",
# and the correction is skipped rather than risk overwriting a human.


def _vikunja_due(task: dict) -> str | None:
    due = task.get("due_date")
    return None if not due or due.startswith("0001-01-01") else due


def _event_matches_pass1(live: dict, p1: dict) -> bool:
    all_day = "date" in live.get("start", {})
    if all_day != bool(p1.get("all_day")):
        return False
    if _norm_title(live.get("summary")) != _norm_title(p1.get("title")):
        return False
    live_start = live["start"].get("dateTime") or live["start"].get("date")
    live_end = live["end"].get("dateTime") or live["end"].get("date")
    if all_day:
        # create_event wrote start[:10] / (end or start)[:10] — mirror that.
        return (_norm_dt(live_start, True) == _norm_dt(p1.get("start"), True)
                and _norm_dt(live_end, True)
                == _norm_dt(p1.get("end") or p1.get("start"), True))
    return (_norm_dt(live_start) == _norm_dt(p1.get("start"))
            and _norm_dt(live_end) == _norm_dt(p1.get("end") or p1.get("start")))


def _task_matches_pass1(live: dict, p1: dict, prefix: str = "") -> bool:
    if _norm_title(live.get("title")) != _norm_title(prefix + (p1.get("title") or "")):
        return False
    return _norm_dt(_vikunja_due(live), True) == _norm_dt(p1.get("due"), True)


# ── The per-item pipeline ──────────────────────────────────────────


async def _delete_refs(refs: list[dict]) -> None:
    for ref in refs:
        if ref["kind"] == "event":
            gcal.delete_event(ref)
        elif ref["kind"] == "task":
            await vikunja.delete_task(ref)
        elif ref["kind"] == "expense":
            store.delete_expense(ref["row_id"])


async def _correct_shopping(item: dict, open_pairs: list[tuple[dict, dict]],
                            strong: dict) -> str | None:
    """Item-level diff: add what the strong model found and the 7B missed,
    remove open items the strong model says should not exist. Checked-off
    items are a human action and are never re-added."""
    p1_norms = {_norm_title(i) for i in (item["pass1_parsed"].get("items") or [])}
    live_norms = {_norm_title(t.get("title")) for _, t in open_pairs}
    strong_items = strong.get("items") or []
    strong_norms = {_norm_title(i) for i in strong_items}

    to_add = [i for i in strong_items
              if _norm_title(i) not in p1_norms | live_norms]
    to_remove = [(ref, t) for ref, t in open_pairs
                 if _norm_title(t.get("title")) not in strong_norms]
    if not to_add and not to_remove:
        return None

    kept = [ref for ref, t in open_pairs if (ref, t) not in to_remove]
    new_tasks = await vikunja.add_shopping_items(to_add) if to_add else []
    new_refs = [telegram._task_ref(t, config.VIKUNJA_SHOPPING_PROJECT_ID)
                for t in new_tasks]
    # New refs are persisted before anything is deleted, so a crash here
    # cannot duplicate items on the next drain.
    store.update_review_ref(item["id"], kept + new_refs)
    for ref, _ in to_remove:
        await vikunja.delete_task(ref)
    parts = [f"+{i}" for i in to_add] + [f"−{t['title']}" for _, t in to_remove]
    return "varer: " + ", ".join(parts)


async def _process(item: dict, now: datetime) -> str | tuple[str, str]:
    """Returns "expired", "done", or ("corrected", description)."""
    rid = item["id"]
    p1 = item["pass1_parsed"]
    refs = item["created_ref"]

    # 1. Hard cap: stranded items (holidays etc.) are dropped un-reviewed.
    if now.timestamp() - item["created_at"] > config.REVIEW_HARD_MAX_AGE_DAYS * 86400:
        store.mark_review(rid, "expired")
        return "expired"

    intent = p1.get("intent")
    live_event = live_task = None
    open_pairs: list[tuple[dict, dict]] = []

    # 2. Does the action still exist, and is it still relevant?
    #    (Relevance is the action's own state — never the queue item's age.)
    if intent == "event":
        live_event = gcal.get_event(refs[0])
        if live_event is None:
            store.mark_review(rid, "expired")
            return "expired"
        # The past-check uses the CREATED end time. If the 7B misparsed the
        # date, the strong model re-parse below will move it — the strong
        # model can only run if we get there, so only clearly-over events
        # (as created) are cleared here; the misparse case is handled by
        # letting still-future events through.
        end_raw = live_event["end"].get("dateTime") or live_event["end"].get("date")
        end_dt = dtparse.parse(end_raw)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=_tz())
        if end_dt < now:
            store.mark_review(rid, "expired")
            return "expired"
    elif intent in ("task", "note"):
        live_task = await vikunja.get_task(refs[0])
        if live_task is None or live_task.get("done"):
            store.mark_review(rid, "expired")
            return "expired"
    elif intent == "shopping":
        for ref in refs:
            t = await vikunja.get_task(ref)
            if t and not t.get("done"):
                open_pairs.append((ref, t))
        if not open_pairs:
            store.mark_review(rid, "expired")
            return "expired"
    elif intent == "expense":
        if store.get_expense(refs[0]["row_id"]) is None:
            store.mark_review(rid, "expired")
            return "expired"
    else:
        store.mark_review(rid, "expired")
        return "expired"

    # 3. Human wins: if the live action no longer matches what Pass 1 made,
    #    the user edited it — never overwrite that.
    edited = False
    if intent == "event":
        edited = not _event_matches_pass1(live_event, p1)
    elif intent in ("task", "note"):
        prefix = "📝 " if intent == "note" else ""
        edited = not _task_matches_pass1(live_task, p1, prefix)
    elif intent == "shopping":
        p1_norms = {_norm_title(i) for i in (p1.get("items") or [p1.get("title")])}
        edited = any(_norm_title(t.get("title")) not in p1_norms for _, t in open_pairs)
    elif intent == "expense":
        row = store.get_expense(refs[0]["row_id"])
        edited = (_norm_title(row["title"]) != _norm_title(p1.get("title"))
                  or abs((row["amount_dkk"] or 0) - (p1.get("amount_dkk") or 0)) > 0.005)
    if edited:
        store.mark_review(rid, "done")
        return "done"

    # 4. Strong-model re-parse, anchored at the ORIGINAL received_at so
    #    relative dates resolve to the same day as Pass 1 did.
    anchor = dtparse.parse(item["received_at"])
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=_tz())
    strong = await llm.parse_message(item["source_text"],
                                     base_url=config.STRONG_OLLAMA_URL,
                                     model=config.STRONG_OLLAMA_MODEL, now=anchor)

    # Mirror telegram's finance gate: expense stays admin-only.
    if strong["intent"] == "expense" and item["chat_id"] != config.TELEGRAM_ADMIN_CHAT_ID:
        strong["intent"] = "note"

    old_fp, new_fp = _fingerprint(p1), _fingerprint(strong)
    if old_fp == new_fp or strong["intent"] in ("question", "unknown"):
        # Same reading — or the strong model punted; deleting a created
        # action on a punt is riskier than leaving it. Fail safe.
        store.mark_review(rid, "done")
        return "done"

    label = p1.get("title") or item["source_text"][:40]
    if new_fp["intent"] != old_fp["intent"]:
        # Intent type switched: create the new action first, persist its ref,
        # THEN delete the old — a crash in between cannot duplicate on re-run.
        _, new_refs = await telegram._execute(strong)
        store.update_review_ref(rid, new_refs)
        await _delete_refs(refs)
        desc = _diff_desc(old_fp, new_fp)
    elif intent == "event":
        gcal.update_event(refs[0], strong)
        desc = _diff_desc(old_fp, new_fp)
    elif intent in ("task", "note"):
        prefix = "📝 " if intent == "note" else ""
        await vikunja.update_task(refs[0], title=prefix + strong["title"],
                                  due=strong.get("due") or "")
        desc = _diff_desc(old_fp, new_fp)
    elif intent == "shopping":
        desc = await _correct_shopping(item, open_pairs, strong)
        if desc is None:  # sets/live state already agree — nothing to change
            store.mark_review(rid, "done")
            return "done"
    else:  # expense
        store.update_expense(refs[0]["row_id"], strong["title"],
                             strong.get("amount_dkk") or 0)
        desc = _diff_desc(old_fp, new_fp)

    # 'corrected' (ikke 'done') så korrektionsraten kan udledes af ægte data
    # fremadrettet; list_pending_reviews ser kun på 'pending', så adfærden
    # er uændret. Markeres først efter at opdateringen lykkedes.
    store.mark_review(rid, "corrected")
    return "corrected", f"»{label}«: {desc}"


async def drain() -> dict:
    """One bounded batch (max 10 items). The agent loops until processed == 0."""
    if not config.STRONG_OLLAMA_URL:
        return {"processed": 0, "corrected": 0}
    if not await llm.is_online(config.STRONG_OLLAMA_URL):
        return {"processed": 0, "corrected": 0, "online": False}

    now = datetime.now(_tz())
    processed = corrected = 0
    notes: dict[int, list[str]] = {}
    for item in store.list_pending_reviews(limit=10):
        try:
            outcome = await _process(item, now)
        except Exception:
            # Leave it pending for the next drain; don't count it as
            # processed, so a batch of only failing items ends the loop.
            log.exception("review of %s failed", item["id"])
            continue
        processed += 1
        # Ambient-stats (DEL 5): ét event pr. pass2-behandling — grundlaget
        # for korrektionsraten ('corrected' vs 'done'; 'expired' = ikke tjekket).
        store.log_event("pass2", outcome if isinstance(outcome, str) else "corrected")
        if isinstance(outcome, tuple):
            corrected += 1
            notes.setdefault(item["chat_id"], []).append(outcome[1])

    for chat_id, lines in notes.items():
        await telegram.send(chat_id, f"🔄 Kvalitetstjek: rettede {len(lines)} ting:\n• "
                                     + "\n• ".join(lines))
    return {"processed": processed, "corrected": corrected}

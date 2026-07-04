"""Aula mail pipeline (Del 3): classify forwarded school mail into calendar
events, task proposals and brief digests.

Security principle (spec §7, layer 1 — the actual guarantee): mail content is
DATA to classify, never commands to obey. This module can only (a) write
proposals, (b) call gcal.create_event / vikunja.create_task with
schema-validated fields after deterministic gating or an explicit button
press. It has no access to the general Telegram intent dispatch, no shell,
and makes no outbound requests based on mail content. Worst case for a
perfect injection: a silly proposal (one tap to reject) or a silly auto
event (one tap to undo).
"""
from __future__ import annotations

import difflib
import logging
from datetime import datetime, time as time_t, timedelta
from email.utils import parseaddr
from zoneinfo import ZoneInfo

from . import config, gcal, gmail, llm, store, telegram, vikunja
from .models import AulaItem, fail_safe_item

log = logging.getLogger("lifehub")


def _tz() -> ZoneInfo:
    return ZoneInfo(config.TZ)


def _now_iso() -> str:
    return datetime.now(_tz()).isoformat(timespec="seconds")


# ── Sender verification ─────────────────────────────────────────────


def sender_verified(from_addr: str) -> bool:
    """Strict suffix match on the From domain: "aula.dk" matches @aula.dk and
    @notify.aula.dk — never @evil-aula.dk (substring match would)."""
    addr = parseaddr(from_addr or "")[1].lower()
    if "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[1]
    for allowed in config.AULA_SENDER_ALLOWLIST:
        a = allowed.lower().lstrip("@").lstrip(".")
        if domain == a or domain.endswith("." + a):
            return True
    return False


# ── Poll: ingest + classify (called under main.py's overlap lock) ──


async def poll_and_process() -> dict:
    """One poll tick. Ingest registers every new mail as status=received
    BEFORE any LLM work (crash-safe resume); classify then works through at
    most GMAIL_MAX_PER_POLL of the backlog, oldest first."""
    new_ids = gmail.sync_new_message_ids()
    ingested = 0
    for mid in new_ids:
        if store.aula_get_message(mid):
            continue  # dubletter fra resync er forventede — historyId-idempotens
        meta = gmail.fetch_headers(mid)
        if meta is None:
            continue
        store.aula_insert_message(
            mid, meta.thread_id, meta.from_addr, meta.subject,
            meta.mail_date.astimezone(_tz()).isoformat(timespec="seconds"),
            sender_verified(meta.from_addr), _now_iso())
        ingested += 1

    processed = 0
    for row in store.aula_received_messages(limit=config.GMAIL_MAX_PER_POLL):
        raw = gmail.fetch_mail(row["message_id"])
        if raw is None:  # slettet i Gmail siden ingest
            store.aula_set_message_status(row["message_id"], "failed")
            continue
        await process_mail(raw, verified=bool(row["sender_verified"]))
        processed += 1
    return {"new": ingested, "processed": processed}


async def process_mail(raw: gmail.RawMail, verified: bool) -> None:
    # Items already exist -> a previous run crashed mid-routing; never create
    # duplicates, close the message instead (the created items stand).
    if store.aula_items_for_message(raw.message_id):
        store.aula_set_message_status(raw.message_id, "classified")
        return
    try:
        items = await llm.classify_email(raw.subject, raw.body_text, raw.mail_date)
    except llm.AulaParseError as exc:
        log.warning("aula %s: parse failed after retry (%s) — fail-safe info",
                    raw.message_id, type(exc).__name__)
        items = [fail_safe_item(raw.subject)]
    # Network/Ollama errors propagate: the row stays 'received' and the next
    # poll retries — a crash mid-LLM never loses or double-processes a mail.

    now = datetime.now(_tz())
    for item in items:
        await _route_item(raw.message_id, item, verified, now)
    store.aula_set_message_status(raw.message_id, "classified")


# ── Routing & gating ────────────────────────────────────────────────


def _item_target_dt(item: AulaItem, now: datetime) -> datetime | None:
    """The moment the item 'happens': deadline, else date (+time unless all-day)."""
    if item.deadline is not None:
        dl = item.deadline
        return dl.replace(tzinfo=_tz()) if dl.tzinfo is None else dl.astimezone(_tz())
    if item.date is not None:
        t = item.time if (item.time and not item.all_day) else time_t(0, 0)
        return datetime.combine(item.date, t, tzinfo=_tz())
    return None


def _is_urgent(item: AulaItem, now: datetime) -> bool:
    target = _item_target_dt(item, now)
    if target is None:
        return False
    if now <= target <= now + timedelta(hours=config.AULA_URGENT_HOURS):
        return True
    # Ting der rammer i dag men "startede" tidligere på dagen (heldags-item,
    # frist i morges) er stadig akut information — ikke stof til i morgen.
    return target.date() == now.date() and target <= now


def _titles_similar(a: str, b: str) -> bool:
    a, b = a.strip().casefold(), b.strip().casefold()
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.75


def _dedupe_hit(item: AulaItem) -> bool:
    """Aula often resends the same message as a reminder: any existing event
    on date ±1 day with a similar title blocks auto-create."""
    try:
        existing = gcal.list_window(item.date.isoformat(), days_around=1)
    except Exception:
        log.exception("aula dedupe lookup failed — failing safe to proposal")
        return True  # kan vi ikke tjekke, må vi ikke auto-oprette
    return any(_titles_similar(e.get("title") or "", item.title) for e in existing)


def _auto_gates(item: AulaItem, verified: bool, now: datetime) -> str | None:
    """None = all gates passed; otherwise the first failed gate (for logs).
    Deterministic gating carries the safety — 7B confidence is just gate 3."""
    if not (config.AULA_AUTO_ENABLED and item.intent in config.AULA_AUTO_INTENTS):
        return "auto_disabled"
    if not verified:
        return "sender_unverified"
    if item.confidence < config.AULA_AUTO_MIN_CONFIDENCE:
        return "low_confidence"
    if item.ambiguity_flags:
        return "ambiguous:" + ",".join(item.ambiguity_flags)
    if item.date is None:
        return "no_date"
    if item.all_day:
        if item.date < now.date():
            return "date_in_past"
    elif item.time is None:
        return "no_time"
    elif datetime.combine(item.date, item.time, tzinfo=_tz()) <= now:
        return "date_in_past"
    if item.date > now.date() + timedelta(days=config.AULA_AUTO_MAX_DAYS_AHEAD):
        return "beyond_horizon"
    if _dedupe_hit(item):
        return "dedupe"
    return None


def _item_to_store(message_id: str, item: AulaItem) -> int:
    return store.aula_insert_item(
        message_id,
        intent=item.intent, title=item.title, summary=item.summary,
        date=item.date.isoformat() if item.date else None,
        time=item.time.isoformat(timespec="minutes") if item.time else None,
        all_day=item.all_day,
        deadline=item.deadline.isoformat() if item.deadline else None,
        confidence=item.confidence, ambiguity_flags=list(item.ambiguity_flags),
        created_at=_now_iso())


async def _route_item(message_id: str, item: AulaItem, verified: bool,
                      now: datetime) -> None:
    item_id = _item_to_store(message_id, item)
    urgent = _is_urgent(item, now)

    if item.intent == "event":
        failed_gate = _auto_gates(item, verified, now)
        log.info("aula item %s (%s): gates %s", item_id, item.intent,
                 "passed" if failed_gate is None else f"stopped at {failed_gate}")
        if failed_gate is None:
            await run_auto_create(item_id, item)
        else:
            await telegram.send_aula_proposal(item_id, store.aula_get_item(item_id),
                                              urgent=urgent)
    elif item.intent == "handling":
        log.info("aula item %s (handling): proposal", item_id)
        await telegram.send_aula_proposal(item_id, store.aula_get_item(item_id),
                                          urgent=urgent)
    else:  # info
        if urgent:
            log.info("aula item %s (info): urgent — notifying now", item_id)
            await telegram.send_aula_urgent_info(store.aula_get_item(item_id))
            store.aula_update_item(item_id, status="notified",
                                   resolved_at=_now_iso())
        else:
            log.info("aula item %s (info): queued for morning brief", item_id)
        # ikke-urgent info bliver stående som pending → næste morgen-brief


# ── Create / undo / approve / reject ────────────────────────────────


def _event_parsed(item: dict) -> dict:
    """Map a stored item row to gcal.create_event's parsed shape."""
    parsed: dict = {"title": item["title"], "all_day": bool(item["all_day"]),
                    "notes": f"Fra Aula: {item['summary']}"}
    if item["all_day"] or not item["time"]:
        parsed["all_day"] = True
        parsed["start"] = item["date"]
        parsed["end"] = item["date"]
    else:
        start = datetime.fromisoformat(f"{item['date']}T{item['time']}")
        parsed["start"] = start.isoformat(timespec="minutes")
        parsed["end"] = (start + timedelta(hours=1)).isoformat(timespec="minutes")
    return parsed


async def run_auto_create(item_id: int, item: AulaItem) -> None:
    row = store.aula_get_item(item_id)
    created = gcal.create_event(_event_parsed(row))
    store.aula_update_item(item_id, status="auto_created",
                           gcal_event_id=created["event_id"],
                           resolved_at=_now_iso())
    await telegram.send_aula_auto_created(item_id, row)


async def approve_item(item_id: int) -> str | None:
    """Button press ✅. Returns a receipt line, or None if not approvable."""
    item = store.aula_get_item(item_id)
    if item is None or item["status"] != "pending":
        return None
    if item["intent"] == "event":
        if not item["date"]:
            return "❌ Forslaget mangler en dato — brug ✏️ Redigér i stedet."
        created = gcal.create_event(_event_parsed(item))
        store.aula_update_item(item_id, status="approved",
                               gcal_event_id=created["event_id"],
                               resolved_at=_now_iso())
        return f"✅ Lagt i kalenderen: {item['title']}"
    if item["intent"] == "handling":
        due = item["deadline"] or item["date"]
        src = "mail" if item.get("stream") == "inbox" else "Aula"
        task = await vikunja.create_task(item["title"], due=due,
                                         description=f"Fra {src}: {item['summary']}")
        store.aula_update_item(item_id, status="approved",
                               vikunja_task_id=task["id"],
                               resolved_at=_now_iso())
        return f"✅ Opgave oprettet: {item['title']}"
    return None  # info-items har ingen godkend-knap


def reject_item(item_id: int) -> bool:
    item = store.aula_get_item(item_id)
    if item is None or item["status"] != "pending":
        return False
    store.aula_update_item(item_id, status="rejected", resolved_at=_now_iso())
    return True


def undo_auto(item_id: int) -> bool:
    """Undo button on an auto-created event. The message row stays processed —
    the mail is never re-classified."""
    item = store.aula_get_item(item_id)
    if item is None or item["status"] != "auto_created" or not item["gcal_event_id"]:
        return False
    gcal.delete_event({"calendar_id": config.DEFAULT_CALENDAR_ID,
                       "event_id": item["gcal_event_id"]})
    store.aula_update_item(item_id, status="undone", resolved_at=_now_iso())
    return True


async def apply_edit(item_id: int, correction: str) -> str:
    """✏️-flow: the user's reply is merged with the original item through the
    ordinary, trusted parse flow — Mikey's text wins over mail-derived fields."""
    item = store.aula_get_item(item_id)
    if item is None or item["status"] != "pending":
        return "Forslaget er udløbet."
    parts = [item["title"]]
    if item["date"]:
        parts.append(f"den {item['date']}")
    if item["time"]:
        parts.append(f"kl. {item['time']}")
    if item["deadline"]:
        parts.append(f"frist {item['deadline'][:16]}")
    combined = (f"{' '.join(parts)}. Rettelse fra Mikey (har forrang): {correction}")
    parsed = await llm.parse_message(combined)
    result, refs = await telegram._execute(parsed)
    kwargs: dict = {}
    for ref in refs:
        if ref.get("kind") == "event":
            kwargs["gcal_event_id"] = ref["event_id"]
        elif ref.get("kind") == "task":
            kwargs["vikunja_task_id"] = ref["task_id"]
    store.aula_update_item(item_id, status="edited", resolved_at=_now_iso(),
                           **kwargs)
    return result


# ── Jobs & brief digest ─────────────────────────────────────────────


def expire_proposals() -> int:
    """Daily 06:00 job: pending proposals older than the TTL -> expired."""
    now = datetime.now(_tz())
    cutoff = (now - timedelta(hours=config.AULA_PROPOSAL_TTL_HOURS)).isoformat(
        timespec="seconds")
    count = store.aula_expire_pending(cutoff, now.isoformat(timespec="seconds"))
    if count:
        log.info("aula: %d proposals expired unanswered", count)
    return count


def collect_brief_digest() -> tuple[list[str], int]:
    """(info lines for the morning brief, proposals expired last 24h).
    Info items are marked briefed and never shown twice."""
    items = store.aula_pending_info()
    lines = [i["title"] for i in items]
    if items:
        store.aula_mark_briefed([i["id"] for i in items],
                                datetime.now(_tz()).isoformat(timespec="seconds"))
    since = (datetime.now(_tz()) - timedelta(hours=24)).isoformat(timespec="seconds")
    return lines, store.aula_expired_since(since)


def feed(days: int = 7) -> dict:
    now = datetime.now(_tz())
    return store.aula_feed((now - timedelta(days=days)).isoformat(timespec="seconds"),
                           now.date().isoformat())

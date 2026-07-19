"""General inbox triage (Del 4): highlight important mail and the actions it
asks for, with deadlines — over the whole INBOX minus noise.

Differences from the Aula pipeline it is built on:
  * Arbitrary senders are fully untrusted, so there is NO auto path at all —
    everything is a highlight or a button proposal. A perfect phishing/
    injection mail can at worst produce a silly proposal (one tap to reject).
  * Admin-only surfaces: proposals and notices go to TELEGRAM_ADMIN_CHAT_ID,
    the dashboard block is gated like the finance block, and the digest is a
    separate admin message — never the family brief.
  * Deterministic noise filter BEFORE the LLM: Gmail's Promotions/Social
    categories and the List-Unsubscribe header never cost a model call.

Shares the aula_messages/aula_items tables (stream='inbox'), the Telegram
callback flow (approve creates a Vikunja task with the deadline as due date),
the proposal TTL and the crash-resume semantics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, gmail, llm, store, telegram
from .models import TriageItem, fail_safe_triage

log = logging.getLogger("lifehub")

_STREAM = "inbox"
_NOISE_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "SPAM", "TRASH"}


def _tz() -> ZoneInfo:
    return ZoneInfo(config.TZ)


def _now_iso() -> str:
    return datetime.now(_tz()).isoformat(timespec="seconds")


def _is_noise(meta: gmail.RawMail) -> bool:
    return bool(_NOISE_LABELS & set(meta.label_ids)) or meta.unsubscribe


async def poll_and_process() -> dict:
    """One poll tick, same shape as aula.poll_and_process. Runs under the
    shared mail lock in main.py so the two streams never overlap the LLM."""
    new_ids = gmail.sync_new_message_ids(stream=_STREAM)
    aula_lid = gmail.aula_label_id()
    ingested = skipped = 0
    for mid in new_ids:
        if store.aula_get_message(mid):
            continue  # allerede set — evt. af aula-streamen
        meta = gmail.fetch_headers(mid)
        if meta is None:
            continue
        if aula_lid and aula_lid in meta.label_ids:
            continue  # Aula-mail i INBOX: aula-streamen ejer den
        noise = _is_noise(meta)
        store.aula_insert_message(
            mid, meta.thread_id, meta.from_addr, meta.subject,
            meta.mail_date.astimezone(_tz()).isoformat(timespec="seconds"),
            sender_verified=False, received_at=_now_iso(), stream=_STREAM,
            status="skipped" if noise else "received")
        skipped += noise
        ingested += not noise

    processed = 0
    for row in store.aula_received_messages(limit=config.GMAIL_MAX_PER_POLL,
                                            stream=_STREAM):
        raw = gmail.fetch_mail(row["message_id"])
        if raw is None:
            store.aula_set_message_status(row["message_id"], "failed")
            continue
        await process_mail(raw)
        processed += 1
    return {"new": ingested, "noise": skipped, "processed": processed}


async def process_mail(raw: gmail.RawMail) -> None:
    if store.aula_items_for_message(raw.message_id):
        store.aula_set_message_status(raw.message_id, "classified")
        return
    try:
        verdict = await llm.classify_inbox_mail(raw.subject, raw.from_addr,
                                                raw.body_text, raw.mail_date)
    except llm.AulaParseError as exc:
        log.warning("triage %s: parse failed after retry (%s) — fail-safe",
                    raw.message_id, type(exc).__name__)
        verdict = fail_safe_triage()
    # Netværksfejl propagerer: rækken forbliver 'received' og prøves igen.

    if verdict.importance == "low" and not verdict.action_required:
        log.info("triage %s: low/no-action (%s) — dropped", raw.message_id,
                 verdict.sender_kind)
        store.aula_set_message_status(raw.message_id, "classified")
        store.log_event("triage", "inbox")  # også droppede mails ER triageret
        return

    await _route(raw, verdict)
    store.aula_set_message_status(raw.message_id, "classified")
    store.log_event("triage", "inbox")  # ambient-stats (DEL 5) — aldrig indhold


def _is_urgent(verdict: TriageItem, now: datetime) -> bool:
    if verdict.deadline is None:
        return False
    dl = verdict.deadline
    dl = dl.replace(tzinfo=_tz()) if dl.tzinfo is None else dl.astimezone(_tz())
    if now <= dl <= now + timedelta(hours=config.AULA_URGENT_HOURS):
        return True
    return dl.date() == now.date() and dl <= now


async def _route(raw: gmail.RawMail, verdict: TriageItem) -> None:
    now = datetime.now(_tz())
    intent = "handling" if verdict.action_required else "info"
    title = (verdict.action_title if verdict.action_required and verdict.action_title
             else raw.subject or "(uden emne)")[:120]
    item_id = store.aula_insert_item(
        raw.message_id, intent=intent, title=title, summary=verdict.summary,
        date=None, time=None, all_day=False,
        deadline=verdict.deadline.isoformat() if verdict.deadline else None,
        confidence=verdict.confidence, ambiguity_flags=[],
        created_at=_now_iso(), stream=_STREAM,
        importance=verdict.importance, sender_kind=verdict.sender_kind)
    urgent = _is_urgent(verdict, now)
    log.info("triage item %s: %s/%s%s", item_id, intent, verdict.importance,
             " URGENT" if urgent else "")

    if verdict.action_required:
        await telegram.send_aula_proposal(item_id, store.aula_get_item(item_id),
                                          urgent=urgent)
    elif urgent or verdict.importance == "high":
        # vigtig ren information: straks-besked til admin, ikke morgendigest
        await telegram.send_post_notice(store.aula_get_item(item_id),
                                        urgent=urgent)
        store.aula_update_item(item_id, status="notified", resolved_at=_now_iso())
    # normal info bliver stående som pending → admin-digest kl. 06:30


def collect_brief_digest() -> tuple[list[str], int]:
    """(digest lines for the admin post message, proposals expired last 24h).
    Same show-once semantics as the Aula digest."""
    items = store.aula_pending_info(stream=_STREAM)
    lines = [f"{i['title']} ({i['sender_kind']})" if i.get("sender_kind")
             else i["title"] for i in items]
    if items:
        store.aula_mark_briefed([i["id"] for i in items],
                                datetime.now(_tz()).isoformat(timespec="seconds"))
    since = (datetime.now(_tz()) - timedelta(hours=24)).isoformat(timespec="seconds")
    return lines, store.aula_expired_since(since, stream=_STREAM)


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

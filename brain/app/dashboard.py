"""Feed refresh jobs + the single aggregate document the PWA consumes.

Privacy model: the finance block is only *included in the response* when the
Cloudflare Access verified email is on the admin list. Other devices never
receive the data at all. The /ambient surface never gets finance regardless.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from . import aula, config, gcal, llm, store, telegram, triage, vikunja
from .feeds import elpris, finance, stubs, weather

log = logging.getLogger("lifehub")


# ── Refresh jobs (called by the scheduler) ──────────────────────────
async def refresh_calendar() -> None:
    try:
        store.set_cache("events", gcal.list_upcoming(7))
        store.set_cache("birthdays", gcal.list_birthdays(30))
    except Exception:
        log.exception("calendar refresh failed")


async def refresh_tasks() -> None:
    try:
        store.set_cache("tasks", await vikunja.open_tasks())
        store.set_cache("tasks_done", await vikunja.done_tasks(hours=48))
    except Exception:
        log.exception("task refresh failed")


async def refresh_weather() -> None:
    try:
        store.set_cache("weather", await weather.fetch())
    except Exception:
        log.exception("weather refresh failed")


async def refresh_elpris() -> None:
    try:
        store.set_cache("elpris", await elpris.fetch())
    except Exception:
        log.exception("elpris refresh failed")


async def refresh_finance() -> None:
    try:
        store.set_cache("finance", await finance.fetch())
    except Exception:
        log.exception("finance refresh failed")


async def morning_brief() -> None:
    """06:30 job: compose the brief, cache it for the dashboard, push to Telegram."""
    ctx = {
        "dato": datetime.now(ZoneInfo(config.TZ)).strftime("%A %d. %B"),
        "kalender_i_dag": [e for e in (store.get_cache("events") or [])
                           if e["start"][:10] == datetime.now(ZoneInfo(config.TZ)).date().isoformat()],
        "opgaver": (store.get_cache("tasks") or [])[:6],
        "foedselsdage": (store.get_cache("birthdays") or [])[:3],
        "vejr": store.get_cache("weather"),
    }
    try:
        text = await llm.compose_brief(ctx)
        # Aula-digest: deterministisk sektion efter LLM-teksten. Info-items
        # medtages én gang (markeres briefed) og vises aldrig igen.
        if config.GMAIL_ENABLED:
            aula_lines, expired = aula.collect_brief_digest()
            if aula_lines:
                text += "\n📧 Aula: " + " · ".join(aula_lines)
            if expired:
                text += f"\n⏳ {expired} Aula-forslag udløb ubesvaret."
        store.set_cache("brief", {"text": text,
                                  "date": datetime.now(ZoneInfo(config.TZ)).date().isoformat()})
        await telegram.broadcast_brief(text)
    except Exception:
        log.exception("morning brief failed")

    # Post-digest (Del 4): egen admin-besked, aldrig familie-briefen —
    # indbakken er privat. Egen try, så en brief-fejl ikke sluger den.
    if config.TRIAGE_ENABLED:
        try:
            post_lines, post_expired = triage.collect_brief_digest()
            if post_lines or post_expired:
                msg = "📮 Post: " + (" · ".join(post_lines) or "ingen nye")
                if post_expired:
                    msg += f"\n⏳ {post_expired} post-forslag udløb ubesvaret."
                await telegram.send_plain(config.TELEGRAM_ADMIN_CHAT_ID, msg)
        except Exception:
            log.exception("post digest failed")


# ── Aggregate document ──────────────────────────────────────────────
def build(viewer_email: str | None, ambient: bool = False) -> dict:
    doc = {
        "generated_at": datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds"),
        "brief": store.get_cache("brief"),
        "events": store.get_cache("events") or [],
        "birthdays": store.get_cache("birthdays") or [],
        "tasks": store.get_cache("tasks") or [],
        "tasks_done": store.get_cache("tasks_done") or [],
        "weather": store.get_cache("weather"),
        "elpris": store.get_cache("elpris"),
    }
    if config.GMAIL_ENABLED:
        try:
            doc["aula"] = aula.feed(days=7)
        except Exception:
            log.exception("aula feed failed")
    is_admin = bool(viewer_email) and viewer_email.lower() in config.ADMIN_EMAILS
    if is_admin and not ambient:
        doc["finance"] = store.get_cache("finance") or {"status": "not_configured"}
        # Post-triage er admin-gated som finance: andre enheder (og /ambient)
        # modtager aldrig blokken.
        if config.TRIAGE_ENABLED:
            try:
                doc["post"] = triage.feed(days=7)
            except Exception:
                log.exception("post feed failed")
    return doc

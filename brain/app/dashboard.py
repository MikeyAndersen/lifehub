"""Feed refresh jobs + the single aggregate document the PWA consumes.

Privacy model: the finance block is only *included in the response* when the
Cloudflare Access verified email is on the admin list. Other devices never
receive the data at all. The /ambient surface never gets finance regardless.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import aula, config, gcal, llm, store, telegram, triage, vikunja
from .feeds import elpris, finance, madplan, stubs, weather

log = logging.getLogger("lifehub")

# Guard: dashboard-load-udløst refresh må ikke overlappe det planlagte poll.
_madplan_lock = asyncio.Lock()


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


async def refresh_madplan() -> None:
    """Poll madplans ugeplan. Ved fejl beholdes seneste cache (vises stale)."""
    if not madplan.enabled() or _madplan_lock.locked():
        return
    async with _madplan_lock:
        try:
            store.set_cache("madplan", await madplan.fetch())
        except Exception:
            log.exception("madplan refresh failed")


async def ensure_fresh_madplan() -> None:
    """Kaldes fire-and-forget ved dashboard-load: refresh hvis cachen mangler
    eller er ældre end stale-grænsen (§3.3: 'poll ... + ved dashboard-load')."""
    if not madplan.enabled():
        return
    mp = store.get_cache_meta("madplan")
    if mp is None or (time.time() - mp[1]) > config.MADPLAN_STALE_MINUTES * 60:
        await refresh_madplan()


def _dinner_brief_line() -> str | None:
    """Morgen-brief-linje (§3.3): 'Aftensmad i dag: X' / 'Ingen madplan for i
    dag' — helt udeladt hvis hele ugen er tom."""
    week = store.get_cache("madplan")
    days = (week or {}).get("days") or []
    if not any(d.get("dish_name") for d in days):
        return None
    today = datetime.now(ZoneInfo(config.TZ)).date().isoformat()
    day = next((d for d in days if d.get("date") == today), None)
    if day and day.get("dish_name") and day.get("status") in ("planned", "cooked"):
        return f"🍽 Aftensmad i dag: {day['dish_name']}"
    return "🍽 Ingen madplan for i dag"


_BRIEF_RETRY_BACKOFF_S = 3


def _brief_context() -> dict:
    now = datetime.now(ZoneInfo(config.TZ))
    return {
        "dato": now.strftime("%A %d. %B"),
        "kalender_i_dag": [e for e in (store.get_cache("events") or [])
                           if e["start"][:10] == now.date().isoformat()],
        "opgaver": (store.get_cache("tasks") or [])[:6],
        "foedselsdage": (store.get_cache("birthdays") or [])[:3],
        "vejr": store.get_cache("weather"),
    }


async def _compose_brief_text(attempts: int) -> str:
    """LLM-narrativ + aftensmadslinje. Genforsøger KUN det flakey LLM-kald —
    Ollama kan være kold eller unåelig et øjeblik, og et enkelt fejlet kald
    var før nok til at efterlade gårsdagens brief hængende. Alt med
    bivirkninger (digest, broadcast) ligger uden for løkken. Kaster hvis
    alle forsøg fejler."""
    ctx = _brief_context()
    last: Exception | None = None
    for i in range(attempts):
        try:
            text = await llm.compose_brief(ctx)
            break
        except Exception as exc:  # noqa: BLE001 — enhver LLM/netværksfejl genforsøges
            last = exc
            log.warning("brief compose forsøg %d/%d fejlede: %s", i + 1, attempts, exc)
            if i < attempts - 1:
                await asyncio.sleep(_BRIEF_RETRY_BACKOFF_S)
    else:
        raise last if last else RuntimeError("brief compose fejlede")
    # Madplan (Fase 2): dagens aftensmad som deterministisk linje.
    dinner = _dinner_brief_line()
    if dinner:
        text += "\n" + dinner
    return text


def _cache_brief(text: str) -> dict:
    payload = {"text": text,
               "date": datetime.now(ZoneInfo(config.TZ)).date().isoformat()}
    store.set_cache("brief", payload)
    return payload


async def morning_brief() -> None:
    """06:30 job: compose (med digests + broadcast), cache, push til Telegram."""
    try:
        text = await _compose_brief_text(attempts=3)
    except Exception:
        log.exception("morning brief failed after retries")
        return
    # Aula-digest: deterministisk sektion efter LLM-teksten. Info-items
    # medtages én gang (markeres briefed) og vises aldrig igen — derfor KUN
    # i det planlagte job, ALDRIG i manuel regenerering (ville spise dem).
    if config.GMAIL_ENABLED:
        try:
            aula_lines, expired = aula.collect_brief_digest()
            if aula_lines:
                text += "\n📧 Aula: " + " · ".join(aula_lines)
            if expired:
                text += f"\n⏳ {expired} Aula-forslag udløb ubesvaret."
        except Exception:
            log.exception("aula digest failed")
    _cache_brief(text)
    try:
        await telegram.broadcast_brief(text)
    except Exception:
        log.exception("brief broadcast failed")

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


async def regenerate_brief() -> bool:
    """Manuel dashboard-regenerering (↻-knappen). Frisk narrativ +
    aftensmadslinje — bevidst UDEN aula/post-digest (de forbruger info-items)
    og UDEN Telegram-broadcast, så en midt-på-dagen-regenerering hverken
    spiser skoleinfo eller spammer familien. True ved succes."""
    try:
        text = await _compose_brief_text(attempts=2)
    except Exception:
        log.exception("manual brief regenerate failed")
        return False
    _cache_brief(text)
    return True


# ── Aggregate document ──────────────────────────────────────────────
def _current_brief() -> dict | None:
    """Kun DAGENS brief vises; en ældre (gårsdagens) skjules, så
    dashboardet aldrig hænger på en forældet brief. Hero falder tilbage
    til 'kommer kl. 06.30'-hintet / regenerér-knappen indtil dagens er klar."""
    brief = store.get_cache("brief")
    today = datetime.now(ZoneInfo(config.TZ)).date().isoformat()
    return brief if brief and brief.get("date") == today else None


def build(viewer_email: str | None, ambient: bool = False) -> dict:
    doc = {
        "generated_at": datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds"),
        "brief": _current_brief(),
        "events": store.get_cache("events") or [],
        "birthdays": store.get_cache("birthdays") or [],
        "tasks": store.get_cache("tasks") or [],
        "tasks_done": store.get_cache("tasks_done") or [],
        "weather": store.get_cache("weather"),
        "elpris": store.get_cache("elpris"),
    }
    # Madplan (§2.2 WeekPlan) — kun med når der findes en cache; markeres
    # `stale` hvis madplan har været utilgængelig længere end grænsen.
    mp = store.get_cache_meta("madplan")
    if mp is not None:
        payload, updated_at = mp
        payload["stale"] = (time.time() - updated_at) > config.MADPLAN_STALE_MINUTES * 60
        doc["madplan"] = payload
    if config.GMAIL_ENABLED:
        try:
            doc["aula"] = aula.feed(days=7)
        except Exception:
            log.exception("aula feed failed")
    is_admin = bool(viewer_email) and viewer_email.lower() in config.ADMIN_EMAILS
    # Signal til frontenden (fx regenerér-brief-knappen); ambient er read-only.
    doc["is_admin"] = is_admin and not ambient
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

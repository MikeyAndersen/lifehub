"""Aggregering til /api/ambient/stats og /api/ambient/events (DEL 5).

Princip: der opfindes ALDRIG tal.
  - Historisk udledbart (ægte fra dag ét): pass1/pass2-fordelingen fra
    review_queue og dagens triagerede mails fra aula_messages.
  - Kun fremadrettet (sys_events-loggen, der begyndte ved `stats_since`):
    prompts, korrektionsrate, Vikunja-writes og travleste time. Indtil
    loggen har data for et tal er værdien None, og frontenden viser
    "indsamler data…".

Aggregeringen caches i procesmemory i 45 s, så orbit-skærmens polling
aldrig belaster SQLite nævneværdigt.
"""
from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config, store

_CACHE_TTL_S = 45
_cache: tuple[float, dict] | None = None


def _now() -> datetime:
    return datetime.now(ZoneInfo(config.TZ))


def _round_rate(corrected: int, checked: int) -> float | None:
    return round(corrected / checked, 4) if checked else None


def _build() -> dict:
    now = _now()
    today = now.date().isoformat()
    since = store.kv_get("stats_since")

    # ── Dual-pass (historisk ægte: review_queue findes siden feature-start) ──
    rq = store.review_status_counts()
    pass1_total = sum(rq.values())                      # alle 7b-parses (CPU)
    pass2_total = pass1_total - rq.get("pending", 0)    # 32b-behandlede (GPU)

    # ── Korrektionsrate (kun sys_events — 'done' før loggen kan have været
    #    korrektioner, så historikken kan ikke bruges retvisende) ──
    corrected = store.count_events("pass2", label="corrected")
    checked = corrected + store.count_events("pass2", label="done")
    correction_rate = _round_rate(corrected, checked)

    # ── Prompts (kun sys_events) — None indtil første er logget ──
    prompts_total = store.count_events("prompt")
    prompts = ({"today": store.count_events("prompt", since_iso=today),
                "total": prompts_total}
               if prompts_total else {"today": None, "total": None})

    # ── Vikunja-writes (kun sys_events) ──
    vikunja_total = store.count_events("vikunja_write")
    vikunja_today = (store.count_events("vikunja_write", since_iso=today)
                     if vikunja_total else None)

    # ── Gmail-triage i dag (historisk ægte fra aula_messages) ──
    triage_today = ((store.message_count("inbox", today)
                     if config.TRIAGE_ENABLED else 0)
                    + (store.message_count("aula", today)
                       if config.GMAIL_ENABLED else 0))

    # ── Highlights: kun dem der har reelt datagrundlag ──
    highlights: list[dict] = []
    histogram = store.event_hour_histogram(today)
    if histogram:
        hour, count = histogram[0]
        highlights.append({"label": "Travleste time i dag",
                           "value": f"kl. {hour}–{int(hour) + 1:02d}",
                           "detail": f"{count} hændelser"})
    recent = store.recent_events(limit=1)
    if recent:
        highlights.append({"label": "Seneste hændelse",
                           "value": recent[-1]["kind"],
                           "detail": recent[-1]["ts"][11:16]})
    if triage_today:
        highlights.append({"label": "Mails behandlet i dag",
                           "value": str(triage_today), "detail": None})

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "collecting_since": since,
        "prompts": prompts,
        "reviews": {
            "pass1_total": pass1_total,
            "pass2_total": pass2_total,
            "pending": rq.get("pending", 0),
            "corrected": corrected if checked else None,
            "checked": checked if checked else None,
            "correction_rate": correction_rate,
        },
        "models": {
            "cpu_7b": {"name": config.OLLAMA_MODEL, "runs": pass1_total},
            "gpu_32b": {"name": config.STRONG_OLLAMA_MODEL, "runs": pass2_total},
        },
        "triage": {"today": triage_today},
        "vikunja": {"writes_today": vikunja_today},
        "highlights": highlights[:3],
    }


def build() -> dict:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL_S:
        return _cache[1]
    doc = _build()
    _cache = (now, doc)
    return doc


def events(after_id: int | None = None, limit: int = 30) -> dict:
    """Seneste system-events til orbit-skærmens event-puls (polling)."""
    evs = store.recent_events(limit=max(1, min(limit, 100)), after_id=after_id)
    return {"events": evs, "last_id": evs[-1]["id"] if evs else (after_id or 0)}

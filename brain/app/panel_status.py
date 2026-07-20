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

from . import config, llm, store

_ollama_cache: tuple[float, bool] | None = None
_strong_cache: tuple[float, bool] | None = None


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


async def _strong_row() -> dict:
    """Den store model (32b) på hoved-pc'en (STRONG_OLLAMA_URL, Pass 2). Tom URL
    = dual-pass slået fra. Ellers pinges endpointet (2,5 s) og caches 60 s, så en
    slukket hoved-pc aldrig forsinker panel-polling: warn = pc offline/utilgængelig."""
    if not config.STRONG_OLLAMA_URL:
        return {"name": "stor model", "state": "off", "detail": "slået fra"}
    global _strong_cache
    now = time.monotonic()
    if _strong_cache is None or now - _strong_cache[0] > 60:
        _strong_cache = (now, await llm.is_online(config.STRONG_OLLAMA_URL))
    online = _strong_cache[1]
    return {"name": "stor model", "state": "ok" if online else "warn",
            "detail": config.STRONG_OLLAMA_MODEL if online else "hoved-pc offline"}


async def build() -> dict:
    services = [
        _cache_row("vikunja", "tasks", warn_after_s=15 * 60),
        _cache_row("kalender", "events", warn_after_s=15 * 60),
        _cache_row("vejr", "weather", warn_after_s=90 * 60),
        _cache_row("madplan", "madplan", warn_after_s=config.MADPLAN_STALE_MINUTES * 60),
        _mail_row("gmail-triage", "inbox", config.TRIAGE_ENABLED),
        _mail_row("aula", "aula", config.GMAIL_ENABLED),
        await _ollama_row(),
        await _strong_row(),
    ]
    return {"generated_at": datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds"),
            "services": services}

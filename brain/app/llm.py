"""Intent parsing and morning-brief composition via a local Ollama model.

Design principles that make a 7B model reliable here:
  1. Structured output — Ollama's `format` parameter takes a JSON schema,
     so the model physically cannot return malformed JSON.
  2. Danish few-shot examples covering relative dates.
  3. Trust nothing — every date the model returns is re-validated in code.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from dateutil import parser as dtparse

from . import config

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["event", "task", "shopping", "expense", "note", "question", "unknown"],
        },
        "title": {"type": "string"},
        "start": {"type": ["string", "null"], "description": "ISO 8601 local datetime"},
        "end": {"type": ["string", "null"]},
        "all_day": {"type": "boolean"},
        "due": {"type": ["string", "null"], "description": "ISO 8601 date for tasks"},
        "amount_dkk": {"type": ["number", "null"]},
        "items": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["intent", "title"],
}

SYSTEM_PROMPT = """Du er parseren i en privat dansk familie-assistent. Du modtager én besked \
(ofte talesprog fra en voicebesked) og returnerer KUN et JSON-objekt der matcher skemaet.

Regler:
- "intent": event = noget med et tidspunkt i kalenderen. task = en to-do. shopping = varer \
der skal købes. expense = en udgift der skal noteres. note = information uden handling. \
question = brugeren spørger om noget. unknown = kan ikke afgøres.
- Datoer/tider skrives som ISO 8601 lokal tid uden tidszone, fx "2026-07-07T14:00".
- Relative udtryk ("på torsdag", "i morgen", "om 14 dage") omregnes ud fra NU-tidspunktet \
du får oplyst. "På torsdag" er den førstkommende torsdag EFTER i dag.
- Events uden sluttid: sæt end = start + 1 time. Heldagsting: all_day = true og tid 00:00.
- Titler er korte og pæne: "Tandlæge", ikke "husk at jeg skal til tandlæge".
- Beløb: kun tallet i DKK.

Eksempler (NU = tirsdag 2026-06-30T18:00):
"husk tandlæge på torsdag klokken 14" ->
{"intent":"event","title":"Tandlæge","start":"2026-07-02T14:00","end":"2026-07-02T15:00","all_day":false,"due":null,"amount_dkk":null,"items":[],"notes":null}
"jeg skal have styr på gødning til plænen i weekenden" ->
{"intent":"task","title":"Gødning til plænen","start":null,"end":null,"all_day":false,"due":"2026-07-04","amount_dkk":null,"items":[],"notes":null}
"køb mælk rugbrød og bleer" ->
{"intent":"shopping","title":"Indkøb","start":null,"end":null,"all_day":false,"due":null,"amount_dkk":null,"items":["Mælk","Rugbrød","Bleer"],"notes":null}
"noter 450 kroner til fodboldstøvler" ->
{"intent":"expense","title":"Fodboldstøvler","start":null,"end":null,"all_day":false,"due":null,"amount_dkk":450,"items":[],"notes":null}
"ungerne har fri fra skole hele fredag" ->
{"intent":"event","title":"Ungerne fri fra skole","start":"2026-07-03T00:00","end":"2026-07-04T00:00","all_day":true,"due":null,"amount_dkk":null,"items":[],"notes":null}
"""


async def _chat(messages: list[dict], schema: dict | None = None, *,
                base_url: str | None = None, model: str | None = None) -> str:
    # Default (no base_url/model) targets the local CPU model and keeps it
    # warm between calls. A non-local base_url is the gaming PC's GPU: there
    # keep_alive is "0" so the model leaves VRAM right after every call.
    remote = base_url is not None and base_url != config.OLLAMA_URL
    body: dict = {"model": model or config.OLLAMA_MODEL, "messages": messages,
                  "stream": False, "keep_alive": "0" if remote else "10m",
                  "options": {"temperature": 0.1}}
    if schema:
        body["format"] = schema
    # 300s: the local 7B model on CPU can be slow to respond, and keep_alive
    # holds it in memory between calls so only the first request pays warm-up.
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{base_url or config.OLLAMA_URL}/api/chat", json=body)
        r.raise_for_status()
        return r.json()["message"]["content"]


async def is_online(base_url: str) -> bool:
    """Quick reachability probe for an Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            r = await client.get(f"{base_url}/api/tags")
            return r.status_code == 200
    except httpx.HTTPError:
        return False


def _validate_dt(value: str | None, now: datetime) -> str | None:
    """Re-check every model-produced datetime: parseable, and not absurd."""
    if not value:
        return None
    try:
        dt = dtparse.parse(value)
    except (ValueError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now.tzinfo)
    # Model date maths goes wrong occasionally — reject anything wildly off.
    if dt < now - timedelta(days=1) or dt > now + timedelta(days=730):
        return None
    return dt.isoformat()


async def parse_message(text: str, *, base_url: str | None = None,
                        model: str | None = None, now: datetime | None = None) -> dict:
    # `now` anchors relative expressions ("på torsdag", "i morgen"). The
    # quality pass re-parses old messages and MUST pass the message's
    # original received_at here — anchoring to the current time would
    # resolve relative dates to a different day and "correct" good events
    # to wrong dates. The same anchor drives _validate_dt's sanity window,
    # or late re-parses would reject dates Pass 1 rightly accepted.
    if now is None:
        now = datetime.now(ZoneInfo(config.TZ))
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(config.TZ))
    user = (
        f"NU er {now.strftime('%A')} {now.isoformat(timespec='minutes')} "
        f"(dansk tid). Besked: {text}"
    )
    raw = await _chat(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        schema=INTENT_SCHEMA, base_url=base_url, model=model,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"intent": "unknown", "title": text[:80]}

    parsed["start"] = _validate_dt(parsed.get("start"), now)
    parsed["end"] = _validate_dt(parsed.get("end"), now)
    parsed["due"] = _validate_dt(parsed.get("due"), now)
    if parsed.get("intent") == "event" and not parsed["start"]:
        # An event without a valid time is really a task.
        parsed["intent"] = "task"
    parsed["source_text"] = text
    return parsed


async def compose_brief(context: dict) -> str:
    """Morning brief: hand the model today's data, get 4-6 friendly Danish lines back."""
    prompt = (
        "Skriv dagens korte morgenbriefing til familien på dansk. Maks 6 linjer, "
        "venlig og konkret, ingen emojis-overload (max 2). Nævn kun det der er i dataene. "
        "Data:\n" + json.dumps(context, ensure_ascii=False, default=str)
    )
    return (await _chat([{"role": "user", "content": prompt}])).strip()

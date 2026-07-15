"""Madplan-feed (Fase 2): poll nova-madplan's ugeplan-API og lad brain cache den.

INTEGRATION_SPEC §3.3/§A5: brain ejer ikke madplan-data — den poller madplans
REST-endpoint og viser seneste cache (evt. `stale`) hvis madplan er nede.
Tom MADPLAN_URL/token = feed slået fra (fail-closed).
"""
import httpx

from .. import config


def enabled() -> bool:
    return bool(config.MADPLAN_URL and config.LIFEHUB_API_TOKEN)


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.LIFEHUB_API_TOKEN}"}


async def fetch() -> dict:
    """GET indeværende uges plan (§2.2 WeekPlan).

    Kaster ved fejl med vilje — kalderen (dashboard.refresh_madplan) beholder
    så den seneste cache i stedet for at overskrive den med ingenting.
    """
    url = f"{config.MADPLAN_URL.rstrip('/')}/api/weekplan/current"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=_headers())
        r.raise_for_status()
        return r.json()


async def inventory() -> list:
    """GET madplans beholdning (Feature B §4.3). Kaster ved fejl med vilje —
    kalderen beholder seneste cache (stale-mønstret, samme som fetch())."""
    url = f"{config.MADPLAN_URL.rstrip('/')}/api/inventory"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=_headers())
        r.raise_for_status()
        return r.json()


async def get_suggestions() -> dict:
    """GET næste uges forslags-sæt (§2.4). Bruges af Telegram-genvejen (Fase 6)."""
    url = f"{config.MADPLAN_URL.rstrip('/')}/api/suggestions/current"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=_headers())
        r.raise_for_status()
        return r.json()


async def accept(day: str, dish_id: int) -> dict:
    """POST accept af ét forslag → skrives ind i ugeplanen (§3.1)."""
    url = f"{config.MADPLAN_URL.rstrip('/')}/api/suggestions/accept"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=_headers(), json={"date": day, "dish_id": dish_id})
        r.raise_for_status()
        return r.json()

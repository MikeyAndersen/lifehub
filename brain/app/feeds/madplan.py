"""Madplan-feed (Fase 2): poll nova-madplan's ugeplan-API og lad brain cache den.

INTEGRATION_SPEC §3.3/§A5: brain ejer ikke madplan-data — den poller madplans
REST-endpoint og viser seneste cache (evt. `stale`) hvis madplan er nede.
Tom MADPLAN_URL/token = feed slået fra (fail-closed).
"""
import httpx

from .. import config


def enabled() -> bool:
    return bool(config.MADPLAN_URL and config.LIFEHUB_API_TOKEN)


async def fetch() -> dict:
    """GET indeværende uges plan (§2.2 WeekPlan).

    Kaster ved fejl med vilje — kalderen (dashboard.refresh_madplan) beholder
    så den seneste cache i stedet for at overskrive den med ingenting.
    """
    url = f"{config.MADPLAN_URL.rstrip('/')}/api/weekplan/current"
    headers = {"Authorization": f"Bearer {config.LIFEHUB_API_TOKEN}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

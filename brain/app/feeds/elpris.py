"""Spot electricity prices from Energi Data Service (free, no key)."""
from datetime import datetime, timedelta

import httpx

from .. import config


async def fetch() -> dict:
    start = datetime.now().strftime("%Y-%m-%dT00:00")
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT23:59")
    params = {
        "start": start, "end": end,
        "filter": '{"PriceArea":["%s"]}' % config.ELPRIS_AREA,
        "sort": "HourDK", "limit": 48,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://api.energidataservice.dk/dataset/Elspotprices",
                             params=params)
        r.raise_for_status()
        rows = r.json().get("records", [])
    hours = [{"hour": x["HourDK"], "dkk_kwh": round(x["SpotPriceDKK"] / 1000, 2)}
             for x in rows if x.get("SpotPriceDKK") is not None]
    now_hour = datetime.now().strftime("%Y-%m-%dT%H:00")
    now_price = next((h["dkk_kwh"] for h in hours if h["hour"].startswith(now_hour[:13])), None)
    return {"now_dkk_kwh": now_price, "hours": hours}

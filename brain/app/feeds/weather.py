"""Weather via Open-Meteo — free, no key."""
import httpx

from .. import config


async def fetch() -> dict:
    params = {
        "latitude": config.LATITUDE, "longitude": config.LONGITUDE,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "timezone": config.TZ, "forecast_days": 3,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        r.raise_for_status()
        d = r.json()
    return {
        "now_c": d["current"]["temperature_2m"],
        "code": d["current"]["weather_code"],
        "wind_ms": d["current"]["wind_speed_10m"],
        "today_max": d["daily"]["temperature_2m_max"][0],
        "today_min": d["daily"]["temperature_2m_min"][0],
        "rain_pct": d["daily"]["precipitation_probability_max"][0],
    }

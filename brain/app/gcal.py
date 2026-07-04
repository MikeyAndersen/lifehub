"""Google Calendar integration. One OAuth refresh token (yours), read across
shared family calendars, write to the shared default calendar."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from . import config
from .google_auth_helper import google_creds


def _service():
    return build("calendar", "v3", credentials=google_creds(), cache_discovery=False)


def list_upcoming(days: int = 7) -> list[dict]:
    now = datetime.now(ZoneInfo(config.TZ))
    return _list_range(now.isoformat(), (now + timedelta(days=days)).isoformat())


def _list_range(t_min: str, t_max: str) -> list[dict]:
    svc = _service()
    events: list[dict] = []
    cal_ids = [c["id"] for c in svc.calendarList().list().execute().get("items", [])
               if c.get("selected", True)]
    for cal_id in cal_ids:
        if cal_id == config.BIRTHDAYS_CALENDAR_ID:
            continue
        resp = svc.events().list(calendarId=cal_id, timeMin=t_min, timeMax=t_max,
                                 singleEvents=True, orderBy="startTime",
                                 maxResults=50).execute()
        for e in resp.get("items", []):
            start = e["start"].get("dateTime") or e["start"].get("date")
            events.append({
                "title": e.get("summary", "(uden titel)"),
                "start": start,
                "all_day": "date" in e["start"],
                "calendar": cal_id,
                "location": e.get("location"),
            })
    events.sort(key=lambda x: x["start"])
    return events


def list_window(day: str, days_around: int = 1) -> list[dict]:
    """Events across selected calendars within ±days_around of an ISO date —
    used by the Aula dedupe gate (reminder mails resent for the same event)."""
    tz = ZoneInfo(config.TZ)
    base = datetime.fromisoformat(day).replace(tzinfo=tz, hour=0, minute=0)
    return _list_range((base - timedelta(days=days_around)).isoformat(),
                       (base + timedelta(days=days_around + 1)).isoformat())


def list_birthdays(days: int = 30) -> list[dict]:
    svc = _service()
    now = datetime.now(ZoneInfo(config.TZ))
    try:
        resp = svc.events().list(
            calendarId=config.BIRTHDAYS_CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=days)).isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=50,
        ).execute()
    except Exception:
        return []
    return [{"title": e.get("summary", ""), "date": e["start"].get("date")}
            for e in resp.get("items", [])]


def _event_body(parsed: dict) -> dict:
    body: dict = {"summary": parsed["title"]}
    if parsed.get("notes"):
        body["description"] = parsed["notes"]
    if parsed.get("all_day"):
        day = parsed["start"][:10]
        end = (parsed.get("end") or parsed["start"])[:10]
        body["start"], body["end"] = {"date": day}, {"date": end}
    else:
        body["start"] = {"dateTime": parsed["start"], "timeZone": config.TZ}
        body["end"] = {"dateTime": parsed.get("end") or parsed["start"], "timeZone": config.TZ}
    return body


def create_event(parsed: dict) -> dict:
    svc = _service()
    created = svc.events().insert(calendarId=config.DEFAULT_CALENDAR_ID,
                                  body=_event_body(parsed)).execute()
    return {"link": created.get("htmlLink", ""),
            "event_id": created["id"],
            "calendar_id": config.DEFAULT_CALENDAR_ID}


def get_event(ref: dict) -> dict | None:
    """Look up an event by created_ref. None if it no longer exists."""
    svc = _service()
    try:
        e = svc.events().get(calendarId=ref["calendar_id"],
                             eventId=ref["event_id"]).execute()
    except Exception:
        return None
    return None if e.get("status") == "cancelled" else e


def update_event(ref: dict, parsed: dict) -> None:
    body = _event_body(parsed)
    # patch() merges nested objects, so explicitly null the unused time field
    # or an all-day <-> timed switch leaves both date and dateTime set.
    for key in ("start", "end"):
        body[key].setdefault("date", None)
        body[key].setdefault("dateTime", None)
    svc = _service()
    svc.events().patch(calendarId=ref["calendar_id"], eventId=ref["event_id"],
                       body=body).execute()


def delete_event(ref: dict) -> None:
    svc = _service()
    try:
        svc.events().delete(calendarId=ref["calendar_id"],
                            eventId=ref["event_id"]).execute()
    except Exception:
        pass  # already gone — deletion is idempotent

"""Google Calendar integration. One OAuth refresh token (yours), read across
shared family calendars, write to the shared default calendar."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import config

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _service():
    creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH, SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_upcoming(days: int = 7) -> list[dict]:
    svc = _service()
    now = datetime.now(ZoneInfo(config.TZ))
    t_min, t_max = now.isoformat(), (now + timedelta(days=days)).isoformat()
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

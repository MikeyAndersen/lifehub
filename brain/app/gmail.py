"""Gmail read-only client for the Aula pipeline (Del 3).

Security principle: mail content is DATA to be classified, never commands to
be obeyed. This module only reads messages under the Aula label, reduces them
to sanitised plain text (URLs replaced with [link: domain], scripts/styling
dropped, control characters stripped, truncated) and hands them on.

Sync strategy: incremental via users.history.list on a stored historyId.
Gmail only keeps history for about a week, so the 404 full-resync fallback
(messages.list, newer_than:GMAIL_LOOKBACK_DAYS) is a normal code path, not an
edge case. Idempotency lives in store.aula_insert_message's unique message_id.
"""
from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import config, store
from .google_auth_helper import google_creds

log = logging.getLogger("lifehub")

_HISTORY_KEY = "gmail_history_id"


@dataclass
class RawMail:
    message_id: str
    thread_id: str
    from_addr: str
    subject: str
    body_text: str
    mail_date: datetime  # tz-aware (Date header; UTC assumed if header is naive)


def _service():
    return build("gmail", "v1", credentials=google_creds(), cache_discovery=False)


def _label_id(svc) -> str:
    """Resolve GMAIL_LABEL (name) to its id. Cached for the process lifetime."""
    global _cached_label_id
    if _cached_label_id is None:
        labels = svc.users().labels().list(userId="me").execute().get("labels", [])
        for lb in labels:
            if lb.get("name", "").casefold() == config.GMAIL_LABEL.casefold():
                _cached_label_id = lb["id"]
                break
        else:
            raise RuntimeError(f"Gmail-label '{config.GMAIL_LABEL}' findes ikke")
    return _cached_label_id


_cached_label_id: str | None = None


# ── Sync: which message ids are new? ───────────────────────────────


def _full_resync_ids(svc, label_id: str) -> list[str]:
    ids: list[str] = []
    token = None
    while True:
        resp = svc.users().messages().list(
            userId="me", labelIds=[label_id],
            q=f"newer_than:{config.GMAIL_LOOKBACK_DAYS}d",
            pageToken=token,
        ).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        token = resp.get("nextPageToken")
        if not token:
            return ids


def _history_ids(svc, label_id: str, start: str) -> tuple[list[str], str]:
    """(new message ids, newest historyId). Raises HttpError 404 when the
    stored historyId has expired — the caller falls back to a full resync."""
    ids: list[str] = []
    newest = start
    token = None
    while True:
        resp = svc.users().history().list(
            userId="me", startHistoryId=start, labelId=label_id,
            historyTypes=["messageAdded"], pageToken=token,
        ).execute()
        newest = resp.get("historyId", newest)
        for h in resp.get("history", []):
            ids += [a["message"]["id"] for a in h.get("messagesAdded", [])]
        token = resp.get("nextPageToken")
        if not token:
            return ids, newest


def sync_new_message_ids() -> list[str]:
    """New message ids under the Aula label since last poll. Persists the
    history cursor; duplicates are harmless (unique message_id in store)."""
    svc = _service()
    label_id = _label_id(svc)
    saved = store.kv_get(_HISTORY_KEY)

    if saved:
        try:
            ids, newest = _history_ids(svc, label_id, saved)
            store.kv_set(_HISTORY_KEY, str(newest))
            return ids
        except HttpError as exc:
            if exc.resp.status != 404:
                raise
            log.info("gmail historyId expired — full resync")

    ids = _full_resync_ids(svc, label_id)
    profile = svc.users().getProfile(userId="me").execute()
    store.kv_set(_HISTORY_KEY, str(profile["historyId"]))
    return ids


# ── Fetch & body extraction ─────────────────────────────────────────


def _header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h.get("name", "").casefold() == name.casefold():
            return h.get("value", "")
    return ""


def _parse_mail_date(value: str) -> datetime:
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_headers(message_id: str) -> RawMail | None:
    """Header-only fetch for the ingest stage (no body). None if deleted."""
    svc = _service()
    try:
        msg = svc.users().messages().get(
            userId="me", id=message_id, format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
    except HttpError as exc:
        if exc.resp.status == 404:
            return None
        raise
    p = msg.get("payload", {})
    return RawMail(message_id=msg["id"], thread_id=msg.get("threadId", ""),
                   from_addr=_header(p, "From"), subject=_header(p, "Subject"),
                   body_text="", mail_date=_parse_mail_date(_header(p, "Date")))


def _walk_parts(part: dict):
    yield part
    for sub in part.get("parts") or []:
        yield from _walk_parts(sub)


def _decode(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", errors="replace")


_URL = re.compile(r"https?://([^\s/<>\"')\]]+)[^\s<>\"')\]]*", re.IGNORECASE)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    text = _URL.sub(lambda m: f"[link: {m.group(1)}]", text)
    text = _CTRL.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()[:config.AULA_MAX_BODY_CHARS]


def extract_body(payload: dict) -> str:
    """Prefer text/plain; Aula mails are HTML-heavy and often have no plain
    part, so fall back to text/html stripped via BeautifulSoup."""
    plain = html = None
    for part in _walk_parts(payload):
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        mime = part.get("mimeType", "")
        if mime == "text/plain" and plain is None:
            plain = _decode(data)
        elif mime == "text/html" and html is None:
            html = _decode(data)
    if plain is None and html is not None:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        plain = soup.get_text("\n")
    return _sanitize(plain or "")


def fetch_mail(message_id: str) -> RawMail | None:
    """Full fetch incl. sanitised body. None if the message is gone."""
    svc = _service()
    try:
        msg = svc.users().messages().get(userId="me", id=message_id,
                                         format="full").execute()
    except HttpError as exc:
        if exc.resp.status == 404:
            return None
        raise
    p = msg.get("payload", {})
    return RawMail(message_id=msg["id"], thread_id=msg.get("threadId", ""),
                   from_addr=_header(p, "From"), subject=_header(p, "Subject"),
                   body_text=extract_body(p),
                   mail_date=_parse_mail_date(_header(p, "Date")))

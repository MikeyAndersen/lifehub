"""Defer-mekanik (panelets 'Senere'): pending + deferred_until i fremtiden
skjules i triage.feed; når fristen er passeret dukker emnet op igen."""
from datetime import datetime, timedelta

from app import triage


def _insert(store, title, *, intent="handling", deferred_until=None):
    item_id = store.aula_insert_item(
        "msg-1", intent=intent, title=title, summary="s", date=None, time=None,
        all_day=False, deadline=None, confidence=0.9, ambiguity_flags=[],
        created_at=datetime.now().isoformat(timespec="seconds"),
        stream="inbox", importance="normal", sender_kind="andet")
    if deferred_until:
        store.aula_update_item(item_id, status="pending",
                               deferred_until=deferred_until)
    return item_id


def test_feed_rows_carry_id_and_deferred_until(db):
    item_id = _insert(db, "Betal elregning")
    feed = triage.feed(days=7)
    row = next(r for r in feed["recent"] if r["title"] == "Betal elregning")
    assert row["id"] == item_id
    assert row["deferred_until"] is None


def test_deferred_item_hidden_until_tomorrow(db):
    tomorrow = (datetime.now() + timedelta(days=1)).replace(microsecond=0)
    _insert(db, "Skjult til i morgen", deferred_until=tomorrow.isoformat())
    feed = triage.feed(days=7)
    assert all(r["title"] != "Skjult til i morgen" for r in feed["recent"])


def test_expired_defer_reappears(db):
    yesterday = (datetime.now() - timedelta(days=1)).replace(microsecond=0)
    _insert(db, "Tilbage igen", deferred_until=yesterday.isoformat())
    feed = triage.feed(days=7)
    assert any(r["title"] == "Tilbage igen" for r in feed["recent"])

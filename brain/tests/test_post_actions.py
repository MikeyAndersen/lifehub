"""Panel-handlinger: approve/arkivér/udsæt + nyhedsbrevs-bulk. Vikunja/gcal
mockes — semantikken (statusser) er det, der testes."""
from datetime import datetime

import pytest

from app import post_actions


def _insert(store, *, intent="handling", sender_kind="andet", status=None):
    item_id = store.aula_insert_item(
        "msg-1", intent=intent, title="Betal elregning", summary="s",
        date=None, time=None, all_day=False, deadline=None, confidence=0.9,
        ambiguity_flags=[], created_at=datetime.now().isoformat(timespec="seconds"),
        stream="inbox", importance="normal", sender_kind=sender_kind)
    if status:
        store.aula_update_item(item_id, status=status)
    return item_id


@pytest.mark.asyncio
async def test_approve_delegates_to_aula(db, monkeypatch):
    called = {}

    async def fake_approve(item_id):
        called["id"] = item_id
        return "✅ Opgave oprettet: Betal elregning"

    monkeypatch.setattr(post_actions.aula, "approve_item", fake_approve)
    item_id = _insert(db)
    result = await post_actions.apply(item_id, "approve")
    assert called["id"] == item_id
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_archive_rejects_item(db):
    item_id = _insert(db)
    result = await post_actions.apply(item_id, "archive")
    assert result["ok"] is True
    assert db.aula_get_item(item_id)["status"] == "rejected"


@pytest.mark.asyncio
async def test_defer_sets_tomorrow_and_keeps_pending(db):
    item_id = _insert(db)
    await post_actions.apply(item_id, "defer")
    item = db.aula_get_item(item_id)
    assert item["status"] == "pending"
    assert item["deferred_until"] > datetime.now().isoformat(timespec="seconds")


@pytest.mark.asyncio
async def test_unknown_action_and_wrong_stream_rejected(db):
    item_id = _insert(db)
    with pytest.raises(post_actions.ActionError) as exc:
        await post_actions.apply(item_id, "explode")
    assert exc.value.status_code == 422
    with pytest.raises(post_actions.ActionError) as exc:
        await post_actions.apply(999999, "archive")
    assert exc.value.status_code == 404


def test_archive_newsletters_only_hits_pending_nyhedsbrev(db):
    a = _insert(db, intent="info", sender_kind="nyhedsbrev")
    b = _insert(db, intent="info", sender_kind="nyhedsbrev", status="briefed")
    c = _insert(db, intent="info", sender_kind="kommune")
    n = db.aula_archive_newsletters(datetime.now().isoformat(timespec="seconds"))
    assert n == 1
    assert db.aula_get_item(a)["status"] == "rejected"
    assert db.aula_get_item(b)["status"] == "briefed"
    assert db.aula_get_item(c)["status"] == "pending"

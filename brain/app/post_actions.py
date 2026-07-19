"""Panel-handlinger på post-triage-emner (Warm Paper handlingspanel).

Tynd delegering: semantikken ejes af aula.approve_item/reject_item — de samme
funktioner som Telegram-knapperne kalder. Modulet tilføjer kun 'defer' og
stream-vagten (kun inbox-emner kan rammes herfra)."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import aula, config, store


class ActionError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def apply(item_id: int, action: str) -> dict:
    item = store.aula_get_item(item_id)
    if item is None or item.get("stream") != "inbox":
        raise ActionError(404, "Ukendt post-emne")
    if action == "approve":
        receipt = await aula.approve_item(item_id)
        if receipt is None:
            raise ActionError(409, "Emnet kan ikke godkendes (ikke pending?)")
        return {"ok": True, "receipt": receipt}
    if action == "archive":
        if item["status"] != "pending":
            raise ActionError(409, "Emnet er allerede afgjort")
        store.aula_update_item(
            item_id, status="rejected",
            resolved_at=datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds"))
        return {"ok": True, "receipt": None}
    if action == "defer":
        if item["status"] != "pending":
            raise ActionError(409, "Emnet er allerede afgjort")
        tomorrow = datetime.now(ZoneInfo(config.TZ)).date() + timedelta(days=1)
        store.aula_update_item(item_id, status="pending",
                               deferred_until=f"{tomorrow.isoformat()}T00:00:00")
        return {"ok": True, "receipt": None}
    raise ActionError(422, f"Ukendt handling: {action}")

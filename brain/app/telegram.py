"""Telegram bot logic, hand-rolled on the Bot API over httpx.

Flow: update arrives on the webhook -> text or transcribed voice -> LLM parse ->
execute immediately against Google Calendar / Vikunja / expense log and reply
with the result. Finance intents are only accepted from the admin chat id.

The older confirmation flow (inline ✅/🗑 buttons via store.add_pending +
_confirm_keyboard, resolved in the callback_query branch of handle_update) is
kept intact: old messages may still fire callbacks, and it can be reinstated.
"""
from __future__ import annotations

import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from . import config, gcal, llm, store, transcribe, vikunja

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"


async def _call(method: str, **params) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API}/{method}", json=params)
        r.raise_for_status()
        return r.json()


async def send(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    params: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = reply_markup
    await _call("sendMessage", **params)


async def send_plain(chat_id: int, text: str,
                     reply_markup: dict | None = None) -> int:
    """No parse_mode: mail-derived text renders harmlessly no matter what
    markup an Aula mail tries to smuggle in. Returns the message_id."""
    params: dict = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = reply_markup
    resp = await _call("sendMessage", **params)
    return resp["result"]["message_id"]


# ── Aula (Del 3): proposals, auto notifications, callbacks ──────────
# Everything mail-derived goes through send_plain. callback_data carries only
# "aula:{action}:{item_id}" (Telegram's 64-byte cap) — never payload.


def _aula_when(item: dict) -> str:
    parts = []
    if item.get("date"):
        parts.append(item["date"])
    if item.get("time") and not item.get("all_day"):
        parts.append(f"kl. {item['time']}")
    elif item.get("all_day"):
        parts.append("(hele dagen)")
    if item.get("deadline"):
        parts.append(f"frist {item['deadline'][:16].replace('T', ' kl. ')}")
    return " ".join(parts)


def _aula_proposal_keyboard(item_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Opret", "callback_data": f"aula:approve:{item_id}"},
        {"text": "✏️ Redigér", "callback_data": f"aula:edit:{item_id}"},
        {"text": "🗑 Afvis", "callback_data": f"aula:reject:{item_id}"},
    ]]}


async def send_aula_proposal(item_id: int, item: dict, urgent: bool = False) -> None:
    kind = "📅 Kalender" if item["intent"] == "event" else "☑️ Opgave"
    lines = [f"{'⚠️ ' if urgent else ''}📧 Aula-forslag — {kind}",
             item["title"]]
    if when := _aula_when(item):
        lines.append(when)
    if item.get("summary"):
        lines.append(item["summary"])
    await send_plain(config.TELEGRAM_ADMIN_CHAT_ID, "\n".join(lines),
                     _aula_proposal_keyboard(item_id))


async def send_aula_auto_created(item_id: int, item: dict) -> None:
    text = (f"📅 Auto-oprettet fra Aula: {item['title']}"
            + (f"\n{w}" if (w := _aula_when(item)) else ""))
    await send_plain(config.TELEGRAM_ADMIN_CHAT_ID, text,
                     {"inline_keyboard": [[
                         {"text": "🗑 Fortryd", "callback_data": f"aula:undo:{item_id}"},
                     ]]})


async def send_aula_urgent_info(item: dict) -> None:
    text = f"⚠️ Aula: {item['title']}"
    if item.get("summary"):
        text += f"\n{item['summary']}"
    for chat_id in config.TELEGRAM_ALLOWED_CHAT_IDS:
        await send_plain(chat_id, text)


async def _handle_aula_callback(cq: dict) -> None:
    from . import aula  # deferred: aula imports this module at load time

    chat_id = cq["message"]["chat"]["id"]
    message_id = cq["message"]["message_id"]
    await _call("answerCallbackQuery", callback_query_id=cq["id"])
    _, action, sid = cq["data"].split(":", 2)
    item = store.aula_get_item(int(sid)) if sid.isdigit() else None
    if item is None:
        await send_plain(chat_id, "Forslaget er udløbet.")
        return

    async def _edit_msg(text: str) -> None:
        await _call("editMessageText", chat_id=chat_id, message_id=message_id,
                    text=text)

    if action == "approve":
        result = await aula.approve_item(item["id"])
        await _edit_msg(result if result else "Forslaget er udløbet.")
    elif action == "reject":
        ok = aula.reject_item(item["id"])
        await _edit_msg(f"🗑 Afvist: {item['title']}" if ok
                        else "Forslaget er udløbet.")
    elif action == "undo":
        ok = aula.undo_auto(item["id"])
        await _edit_msg(f"🗑 Fortrudt — {item['title']} er slettet fra kalenderen."
                        if ok else "Kunne ikke fortryde — eventet er måske allerede væk.")
    elif action == "edit":
        prompt_id = await send_plain(chat_id, f"✏️ {item['title']}\n"
                                     "Skriv rettelsen som svar på denne besked.")
        store.kv_set(f"aula_edit:{chat_id}:{prompt_id}", str(item["id"]))


async def _maybe_handle_aula_edit_reply(msg: dict, text: str) -> bool:
    """A reply to one of our ✏️ prompts carries the correction. True = handled."""
    reply_to = (msg.get("reply_to_message") or {}).get("message_id")
    if not reply_to:
        return False
    key = f"aula_edit:{msg['chat']['id']}:{reply_to}"
    item_id = store.kv_get(key)
    if not item_id:
        return False
    from . import aula  # deferred: aula imports this module at load time
    store.kv_del(key)
    result = await aula.apply_edit(int(item_id), text)
    await send_plain(msg["chat"]["id"], result)
    return True


def _confirm_keyboard(pid: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Opret", "callback_data": f"ok:{pid}"},
        {"text": "🗑 Drop", "callback_data": f"drop:{pid}"},
    ]]}


def _describe(parsed: dict) -> str:
    kind = {"event": "📅 Kalender", "task": "☑️ Opgave", "shopping": "🛒 Indkøb",
            "expense": "💸 Udgift", "note": "📝 Note"}.get(parsed["intent"], "❓")
    lines = [f"{kind}: <b>{parsed['title']}</b>"]
    if parsed.get("start"):
        lines.append(f"Start: {parsed['start'][:16].replace('T', ' kl. ')}")
    if parsed.get("due"):
        lines.append(f"Frist: {parsed['due'][:10]}")
    if parsed.get("items"):
        lines.append("Varer: " + ", ".join(parsed["items"]))
    if parsed.get("amount_dkk"):
        lines.append(f"Beløb: {parsed['amount_dkk']:.0f} kr.")
    return "\n".join(lines)


def _task_ref(task: dict, project_id: int) -> dict:
    return {"kind": "task", "project_id": task.get("project_id") or project_id,
            "task_id": task["id"]}


async def _execute(parsed: dict) -> tuple[str, list[dict]]:
    """Create the action for a parsed intent. Returns (user message,
    created_ref list) — the refs let the quality pass update/delete later."""
    intent = parsed["intent"]
    if intent == "event":
        created = gcal.create_event(parsed)
        ref = {"kind": "event", "calendar_id": created["calendar_id"],
               "event_id": created["event_id"]}
        return f"✅ Lagt i kalenderen.\n{created['link']}", [ref]
    if intent == "task":
        task = await vikunja.create_task(parsed["title"], due=parsed.get("due"),
                                         description=parsed.get("notes") or "")
        return "✅ Opgave oprettet.", [_task_ref(task, config.VIKUNJA_DEFAULT_PROJECT_ID)]
    if intent == "shopping":
        tasks = await vikunja.add_shopping_items(parsed.get("items") or [parsed["title"]])
        refs = [_task_ref(t, config.VIKUNJA_SHOPPING_PROJECT_ID) for t in tasks]
        return "✅ Sat på indkøbslisten.", refs
    if intent == "expense":
        row_id = store.log_expense(parsed["title"], parsed.get("amount_dkk") or 0,
                                   datetime.now(ZoneInfo(config.TZ)).isoformat(),
                                   parsed.get("source_text", ""))
        return "✅ Udgift noteret.", [{"kind": "expense", "row_id": row_id}]
    if intent == "note":
        task = await vikunja.create_task(f"📝 {parsed['title']}",
                                         description=parsed.get("source_text", ""))
        return "✅ Note gemt som opgave.", [_task_ref(task, config.VIKUNJA_DEFAULT_PROJECT_ID)]
    return "🤷 Det fangede jeg ikke — prøv at omformulere.", []


def _maybe_enqueue(parsed: dict, chat_id: int, created_ref: list[dict]) -> None:
    """Queue the Pass-1 result for the strong-model quality pass. No-op when
    STRONG_OLLAMA_URL is unset or nothing was created (question/unknown)."""
    if not config.STRONG_OLLAMA_URL or not created_ref:
        return
    store.enqueue_review(parsed.get("source_text", ""), chat_id, parsed,
                         datetime.now(ZoneInfo(config.TZ)).isoformat(), created_ref)


async def _download_voice(file_id: str) -> str:
    info = await _call("getFile", file_id=file_id)
    path = info["result"]["file_path"]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{FILE_API}/{path}")
        r.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    tmp.write(r.content)
    tmp.close()
    return tmp.name


async def handle_update(update: dict) -> None:
    # ── Button presses ───────────────────────────────────────────
    if cq := update.get("callback_query"):
        chat_id = cq["message"]["chat"]["id"]
        if chat_id not in config.TELEGRAM_ALLOWED_CHAT_IDS:
            return
        if cq.get("data", "").startswith("aula:"):
            await _handle_aula_callback(cq)
            return
        action, _, pid = cq["data"].partition(":")
        parsed = store.pop_pending(pid)
        await _call("answerCallbackQuery", callback_query_id=cq["id"])
        if not parsed:
            await send(chat_id, "Den er udløbet — send beskeden igen.")
            return
        if action == "ok":
            result, created_ref = await _execute(parsed)
            _maybe_enqueue(parsed, chat_id, created_ref)
            await send(chat_id, result)
        else:
            await send(chat_id, "Droppet 👍")
        return

    # ── Messages ─────────────────────────────────────────────────
    msg = update.get("message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    if chat_id not in config.TELEGRAM_ALLOWED_CHAT_IDS:
        await send(chat_id, "Denne bot er privat.")
        return

    if voice := (msg.get("voice") or msg.get("audio")):
        path = await _download_voice(voice["file_id"])
        text = transcribe.transcribe(path)
        if not text:
            await send(chat_id, "Kunne ikke høre noget i den voicebesked 🎙")
            return
        await send(chat_id, f"🎙 Jeg hørte: “{text}”")
    else:
        text = (msg.get("text") or "").strip()
    if not text:
        return

    if text.startswith("/start"):
        await send(chat_id, "Hej! Send mig tekst eller en voicebesked — jeg laver det "
                            "om til kalenderaftaler, opgaver eller indkøb.")
        return

    # Svar på en ✏️ Aula-redigér-prompt fanges før det almindelige flow.
    if await _maybe_handle_aula_edit_reply(msg, text):
        return

    parsed = await llm.parse_message(text)

    # Finance is Mikey-only: silently downgrade for everyone else.
    if parsed["intent"] == "expense" and chat_id != config.TELEGRAM_ADMIN_CHAT_ID:
        parsed["intent"] = "note"

    # Execute immediately instead of asking for confirmation. The confirm flow
    # (store.add_pending + _confirm_keyboard, handled by the callback_query
    # branch above) is kept intact so old inline buttons still work and the
    # flow can be reinstated later.
    result, created_ref = await _execute(parsed)
    _maybe_enqueue(parsed, chat_id, created_ref)
    await send(chat_id, f"{_describe(parsed)}\n\n{result}")


async def broadcast_brief(text: str) -> None:
    for chat_id in config.TELEGRAM_ALLOWED_CHAT_IDS:
        await send(chat_id, f"☀️ <b>Dagens brief</b>\n{text}")

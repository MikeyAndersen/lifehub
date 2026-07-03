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

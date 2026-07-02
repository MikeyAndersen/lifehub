"""Telegram bot logic, hand-rolled on the Bot API over httpx.

Flow: update arrives on the webhook -> text or transcribed voice -> LLM parse ->
pending confirmation with inline buttons -> ✅ executes against Google Calendar /
Vikunja / expense log. Finance intents are only accepted from the admin chat id.
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


async def _execute(parsed: dict) -> str:
    intent = parsed["intent"]
    if intent == "event":
        link = gcal.create_event(parsed)
        return f"✅ Lagt i kalenderen.\n{link}"
    if intent == "task":
        await vikunja.create_task(parsed["title"], due=parsed.get("due"),
                                  description=parsed.get("notes") or "")
        return "✅ Opgave oprettet."
    if intent == "shopping":
        await vikunja.add_shopping_items(parsed.get("items") or [parsed["title"]])
        return "✅ Sat på indkøbslisten."
    if intent == "expense":
        store.log_expense(parsed["title"], parsed.get("amount_dkk") or 0,
                          datetime.now(ZoneInfo(config.TZ)).isoformat(),
                          parsed.get("source_text", ""))
        return "✅ Udgift noteret."
    if intent == "note":
        await vikunja.create_task(f"📝 {parsed['title']}",
                                  description=parsed.get("source_text", ""))
        return "✅ Note gemt som opgave."
    return "🤷 Det fangede jeg ikke — prøv at omformulere."


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
        await send(chat_id, await _execute(parsed) if action == "ok" else "Droppet 👍")
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

    pid = store.add_pending(parsed)
    await send(chat_id, _describe(parsed), reply_markup=_confirm_keyboard(pid))


async def broadcast_brief(text: str) -> None:
    for chat_id in config.TELEGRAM_ALLOWED_CHAT_IDS:
        await send(chat_id, f"☀️ <b>Dagens brief</b>\n{text}")

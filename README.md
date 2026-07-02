# LifeHub

Self-hosted family life dashboard + Telegram assistant. Voice or text messages become
calendar events, tasks, shopping items and expense notes — parsed by a **local** LLM
(Ollama), so there are no API costs. One aggregate API feeds a PWA with two layouts:
an interactive dashboard and a read-only ambient view for Wallpaper Engine / a kitchen
tablet.

```
Telegram (voice/text) ──▶ brain (FastAPI) ──▶ Google Calendar (family, shared)
                              │                Vikunja (tasks + shopping)
                              │                SQLite (expenses, feed cache)
      Ollama + faster-whisper ┘
                              ▼
                    /api/dashboard  ──▶ Astro PWA  (interactive, per-user)
                    /api/ambient    ──▶ /ambient   (wallpaper/tablet, never finance)
```

**Privacy model:** Cloudflare Access authenticates every request and injects
`Cf-Access-Authenticated-User-Email`. The finance block is only *included in the JSON*
for emails in `ADMIN_EMAILS` — other devices never receive it. `/api/ambient` never
contains finance for anyone, because wallpapers and kitchen tablets are shared surfaces.

## Setup

### 1. Telegram bot
1. Talk to **@BotFather** → `/newbot` → copy the token into `.env`.
2. Find your chat id (message **@userinfobot**) and add family ids to
   `TELEGRAM_ALLOWED_CHAT_IDS`; yours also goes in `TELEGRAM_ADMIN_CHAT_ID`.
3. After the brain is running behind your Cloudflare tunnel, register the webhook:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://lifehub.dit-domæne.dk/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>"
   ```
   Note: the webhook path must be **excluded from Cloudflare Access** (Telegram can't
   log in) — add a bypass policy for `/telegram/webhook/*`. The secret in the path is
   what protects it.

### 2. Google Calendar
Run `brain/scripts/google_auth.py` once on your PC (instructions in the file header),
then copy the resulting `token.json` to `lifehub/secrets/token.json` on the server.
Create a shared **Familien** calendar in Google Calendar, share it with the family,
and put its calendar id in `DEFAULT_CALENDAR_ID`.

### 3. Bring it up
```bash
cp .env.example .env   # fill it in
docker compose up -d --build
docker exec -it lifehub-ollama ollama pull qwen2.5:7b-instruct
```
First visit Vikunja on :3456, create your user, projects for tasks + shopping, and an
API token (Settings → API tokens) → put token and project ids in `.env`, then
`docker compose restart brain`.

### 4. Dashboard
```bash
cd dashboard && npm install && npm run build
```
Serve `dashboard/dist/` with your usual static setup (or `npm run dev` locally — the
dev server proxies `/api` to `localhost:8300`). In production, route `/api/*` and
`/telegram/*` to the brain (port 8300) and everything else to the static files, all
behind the same Cloudflare tunnel + Access application.

### 5. Wallpaper Engine
Wallpaper Engine → Create → **Web** wallpaper → point it at
`https://lifehub.dit-domæne.dk/ambient`. Since Access sits in front, either add a
service-token bypass for the `/ambient` path + `/api/ambient`, or keep it LAN-only and
use the internal address. The kitchen tablet uses the same URL via Home Assistant cast.

## Testing without Telegram
```bash
curl localhost:8300/api/dashboard          # aggregate document
curl -X POST localhost:8300/api/brief/run \
     -H "Cf-Access-Authenticated-User-Email: you@example.dk"   # trigger morning brief
```

## Roadmap (matches the phased plan)
- **Phase 1 (this repo):** Telegram → calendar/tasks/shopping/expenses, dashboard,
  ambient view, morning brief at 06:30 with Telegram push.
- **Phase 2:** GoCardless bank data (`feeds/finance.py`), madplan + transit widgets
  (`feeds/stubs.py`), weather/elpris already live.
- **Phase 3:** Aula, affaldshentning, TTS-brief to the kitchen tablet via HA.
- **Phase 4:** Restyle with the Claude Design mockup — all colours/typography live in
  `dashboard/src/styles/global.css` as tokens, so a redesign is mostly a token swap.

## Notes
- Whisper `medium` is accurate for Danish but slow on CPU; drop to `small` if voice
  notes take too long. The webhook answers Telegram instantly and does the heavy work
  in the background, so nothing times out either way.
- Every LLM-produced date is re-validated in code (`llm._validate_dt`); the ✅/🗑
  confirmation in Telegram is the final safety net.
- Nightly calendar mirror to SQLite (data-sovereignty backup) is an easy add: a
  scheduler job that dumps `gcal.list_upcoming(365)` into the cache table.

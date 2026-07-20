# LifeHub

Self-hosted family life dashboard + Telegram assistant. Voice or text messages become
calendar events, tasks, shopping items and expense notes — parsed by a **local** LLM
(Ollama), so there are no API costs. Forwarded mail (Aula + general inbox) is triaged by
the same local model into calendar events, task proposals and morning-brief highlights.
One aggregate API feeds a PWA that renders several read-only display surfaces plus the
interactive dashboard.

```
Telegram (voice/text) ─┐
Gmail: Aula label      ├▶ brain (FastAPI) ──▶ Google Calendar (family, shared)
Gmail: general inbox   ┘        │              Vikunja (tasks + shopping)
                                │              SQLite (expenses, feed + mail cache)
        Ollama + faster-whisper ┘
                                ▼
              /api/dashboard  ──▶  /                 interactive, per-user
              /api/ambient    ──▶  /ambient          space ambient (wallpaper/tablet)
                                   /ambient/orbit     orbit observatory
                                   /paper/tablet      Warm Paper family dashboard
                                   /paper/wallpaper   Warm Paper ultrawide wallpaper
              (+admin feeds)  ──▶  /paper/panel       Warm Paper action panel
```

**Privacy model:** Cloudflare Access authenticates every request and injects
`Cf-Access-Authenticated-User-Email`. The finance block is only *included in the JSON*
for emails in `ADMIN_EMAILS` — other devices never receive it, and it never appears on
**any** ambient or paper surface. `/api/ambient` never contains finance **or** mail
(post/Aula) for anyone, because wallpapers and kitchen tablets are shared surfaces. The
Warm Paper **panel** is the one interactive display surface and is admin-gated per action.

## Surfaces (open these in a browser)

All pages are served from the same origin as the API, so use your deployed base URL
(`https://lifehub.nova-tech.dk`) or, for the shared surfaces, the LAN address via caddy
(`http://192.168.0.145:8080`, see [docs/OPERATIONS.md](docs/OPERATIONS.md)).

| Link | Surface | What it is | Finance / mail |
|---|---|---|---|
| [`/`](https://lifehub.nova-tech.dk/) | **Dashboard** | Interactive, phone-first per-user view: brief, calendar, tasks, Aula, post, madplan, beholdning, transit. Task checkboxes write back to Vikunja. | Finance shown to `ADMIN_EMAILS` only |
| [`/ambient`](https://lifehub.nova-tech.dk/ambient) | **Ambient · rum-ur** | Read-only shared surface for Wallpaper Engine / kitchen tablet. Auto-picks ultrawide (5120×1440 with solar-system “wings”) or tablet (1920×1200) by aspect ratio. | Never |
| [`/ambient/orbit`](https://lifehub.nova-tech.dk/ambient/orbit) | **Ambient · orbit** | Full-screen “observatory”: living planet driven by real sunrise/sunset + weather, event particles, and live system stats (LLM passes, triage counts, prompts). | Never |
| [`/paper/tablet`](https://lifehub.nova-tech.dk/paper/tablet) | **Warm Paper · tablet** | Secondary warm-paper theme (URL-selected): family dashboard for a docked Pixel Tablet, 2560×1600, with automatic day/night. Pure display. | Never |
| [`/paper/wallpaper`](https://lifehub.nova-tech.dk/paper/wallpaper) | **Warm Paper · wallpaper** | Ultrawide ambient layer (5120×1440) that sits behind windows — calm drift, next days, weather. Auto day↔night on sunrise/sunset. Pure display. | Never |
| [`/paper/wallpaper/dark`](https://lifehub.nova-tech.dk/paper/wallpaper/dark) | **Warm Paper · wallpaper (dark)** | Same surface, forced dark palette 24/7 (ignores sunrise/sunset). | Never |
| [`/paper/panel`](https://lifehub.nova-tech.dk/paper/panel) | **Warm Paper · panel** | Interactive triage panel (1920×1080): approve / archive / defer inbox items, a DRIFT status footer. Auto day↔night. **Admin only** (or a trusted device via `PANEL_INBOX_OPEN`). | Post shown; finance never |
| [`/paper/panel/dark`](https://lifehub.nova-tech.dk/paper/panel/dark) | **Warm Paper · panel (dark)** | Same panel, forced dark palette 24/7. **Admin only** (or a trusted device via `PANEL_INBOX_OPEN`). | Post shown; finance never |

From the interactive dashboard, the **“Ambient visning ▾”** menu in the top bar links to
every surface above.

## API endpoints (brain, port 8300)

Everything under `/api/*` sits behind Cloudflare Access; `/telegram/webhook/*` is bypassed
(the path secret protects it). Admin-gated routes require an `ADMIN_EMAILS` identity.

| Method & path | Purpose |
|---|---|
| `GET /healthz` | Liveness probe |
| `GET /api/dashboard` | Full per-user aggregate document (finance for admins) |
| `GET /api/ambient` | Shared-surface document — no finance, no mail |
| `GET /api/ambient/stats` | Orbit system stats (LLM passes, triage/prompt counters), cached 45 s |
| `GET /api/ambient/events` | Orbit event pulse (`after_id` cursor; only `kind`/`label`) |
| `POST /api/tasks/{id}/done` | Checkbox write-back to Vikunja |
| `POST /api/brief/run` | *(admin)* Run the full 06:30 morning brief now |
| `POST /api/brief/regenerate` | *(admin)* Regenerate only today’s brief text |
| `POST /api/aula/poll` | *(test)* Poll the Aula mail stream now |
| `GET /api/aula/info` | Aula info items + recent proposals/autos |
| `POST /api/post/poll` | *(test)* Poll the general-inbox triage stream now |
| `GET /api/panel/feed` | Panel feed — like `/api/dashboard` incl. `post`, but **never** finance; serves the inbox without a login when `PANEL_INBOX_OPEN=true` |
| `POST /api/post/{id}/action` | *(admin / panel)* Panel action: `approve` / `archive` / `defer` |
| `POST /api/post/archive-newsletters` | *(admin / panel)* Archive the collapsed newsletter row |
| `GET /api/panel/status` | *(admin / panel)* DRIFT footer metrics for the panel |
| `POST /telegram/webhook/{secret}` | Telegram webhook (Access-bypassed) |
| `POST /api/review/drain` | GPU boot agent — Pass-2 review drain (token-gated) |
| `GET /api/internal/inventory` | Madplan inventory proxy (token-gated) |

## Setup

### 1. Telegram bot
1. Talk to **@BotFather** → `/newbot` → copy the token into `.env`.
2. Find your chat id (message **@userinfobot**) and add family ids to
   `TELEGRAM_ALLOWED_CHAT_IDS`; yours also goes in `TELEGRAM_ADMIN_CHAT_ID`.
3. After the brain is running behind your Cloudflare tunnel, register the webhook:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://lifehub.nova-tech.dk/telegram/webhook/<TELEGRAM_WEBHOOK_SECRET>"
   ```
   Note: the webhook path must be **excluded from Cloudflare Access** (Telegram can't
   log in) — add a bypass policy for `/telegram/webhook/*`. The secret in the path is
   what protects it.

### 2. Google Calendar + Gmail
Run `brain/scripts/google_auth.py` once on your PC (instructions in the file header) with
both the `calendar` and `gmail.readonly` scopes, then copy the resulting `token.json` to
`lifehub/secrets/token.json` on the server. Create a shared **Familien** calendar in
Google Calendar, share it with the family, and put its calendar id in
`DEFAULT_CALENDAR_ID`. For the Aula / inbox mail streams, see
[docs/OPERATIONS.md](docs/OPERATIONS.md) (label + filter setup, `.env` flags).

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

### 5. Wallpaper Engine / kitchen tablet
The ambient and paper surfaces are meant for Wallpaper Engine and a Home Assistant kitchen
cast. Rather than pierce Cloudflare Access, point them **directly at caddy over the LAN**
(these surfaces carry no finance and no mail by design). A ready wrapper project lives in
`ops/wallpaper-engine/lifehub-ambient/`; the full walkthrough (including the paper URLs) is
in [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Testing without Telegram
```bash
curl localhost:8300/api/dashboard          # aggregate document
curl -X POST localhost:8300/api/brief/run \
     -H "Cf-Access-Authenticated-User-Email: you@example.dk"   # trigger morning brief
```
Local dev without uvicorn: exercise the app with `starlette.testclient.TestClient`
(`raise_server_exceptions=False`; boot-time gcal/vikunja refresh failures are expected
without creds). Backend tests: `cd brain && python -m pytest`.

## Current state
- **Assistant:** Telegram voice/text → calendar / tasks / shopping / expenses, with a
  local LLM, deterministic Danish date resolver, and a ✅/✏️/🗑 confirmation safety net.
- **Mail triage:** Aula stream (auto behind deterministic gates) and general inbox stream
  (proposals only, admin-gated) — see [docs/OPERATIONS.md](docs/OPERATIONS.md).
- **Feeds:** weather, elpris, GoCardless finance (admins only), madplan + beholdning,
  transit. Morning brief at 06:30 with Telegram push.
- **Surfaces:** interactive dashboard, space ambient + orbit observatory, and the Warm
  Paper theme (tablet / wallpaper / interactive panel). See the table above.
- **Data flywheel:** the parser learns from its own corrected/confirmed messages; a
  GPU-agent Pass 2 can re-review the queue (`/api/review/drain`).

Planned / easy adds: nightly calendar mirror to SQLite (dump `gcal.list_upcoming(365)`
into the cache table for data-sovereignty backup), TTS brief to the kitchen tablet via HA.

## Notes
- Whisper `medium` is accurate for Danish but slow on CPU; drop to `small` if voice
  notes take too long. The webhook answers Telegram instantly and does the heavy work
  in the background, so nothing times out either way.
- Every LLM-produced date is re-validated in code; mail content is treated as **data,
  never commands** (schema-validated LLM output, parameterized SQL, bodies never stored).
- Colours, typography and motion live as tokens in `dashboard/src/styles/global.css`
  (space theme) and `dashboard/src/styles/paper.css` (Warm Paper), so a restyle is
  mostly a token swap.

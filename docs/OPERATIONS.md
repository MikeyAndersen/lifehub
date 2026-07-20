# LifeHub — Operations

Driftsnoter for de dele der kræver manuel opsætning eller har kendte
faldgruber. (Startet med Del 3 — Aula/Gmail-indlæsning; udvid gerne.)

## Aula/Gmail-indlæsning (Del 3)

### Arkitektur i én linje

Aula-beskeder videresendes til Gmail → brain poller `Aula`-labelet →
mail saneres og klassificeres af den lokale LLM (event/handling/info) →
auto-oprettelse bag deterministiske gates, ellers Telegram-forslag med
✅/✏️/🗑-knapper; info samles i morgen-briefen. **Ingen Aula-scraping,
intet MitID** — mail-videresendelsen er hele integrationen.

### Engangsopsætning

1. **OAuth-udvidelse** (gmail.readonly oveni calendar):
   ```bash
   cp /opt/lifehub/secrets/token.json /opt/lifehub/secrets/token.json.bak
   # på din egen maskine, i brain/scripts/:
   python google_auth.py     # ny consent — token.json får begge scopes
   # kopiér token.json til serveren og test at kalenderen stadig virker
   ```
   Fejler refresh bagefter med `invalid_grant`: slet token og kør auth forfra.
2. **Gmail-label og filter:**
   - Opret label `Aula`.
   - **Verificér først** den reelle `From`-header på en ægte videresendt
     Aula-mail ("Show original"). Auto-forward bevarer typisk original
     afsender; er det en anden adresse, justér både filteret og
     `AULA_SENDER_ALLOWLIST`.
   - Filter: `from:(aula.dk)` → *Apply label: Aula* (evt. *Skip Inbox*).
3. **.env:** se `Gmail / Aula`-blokken i `.env.example`. Husk at
   `.env`-ændringer kræver `docker compose down && docker compose up -d`
   (ikke `restart`).

### Udrulning (forslag-only først)

Kør 1–2 uger med `AULA_AUTO_ENABLED=false`. Gate-resultater logges pr. item
(`aula item N gates: stopped at low_confidence` osv.) — kalibrér
`AULA_AUTO_MIN_CONFIDENCE` ud fra dem, og slå så auto til. Auto gælder kun
`event` (v1); `handling` er bevidst altid forslag.

### Manuel test

```bash
# send en testmail til dig selv, giv den Aula-label, og:
curl -X POST http://192.168.0.145:8300/api/aula/poll
curl http://192.168.0.145:8300/api/aula/info?days=7
```

### Faldgruber

- **historyId udløber** (~en uge hos Gmail) → 404 → fuld resync via
  `messages.list(newer_than:GMAIL_LOOKBACK_DAYS)`. Det er en normal kodesti,
  ikke en fejl. Idempotens via unik `message_id` — resync giver aldrig
  dubletter.
- **HTML-only mails:** Aula-mails mangler ofte `text/plain`-part; body
  udtrækkes fra HTML via BeautifulSoup og saneres (URL'er → `[link: domæne]`,
  kontroltegn væk, trunkeret til `AULA_MAX_BODY_CHARS`).
- **Afsender-verifikation** er streng suffix-match på domænet:
  `aula.dk` matcher `@aula.dk` og `@notify.aula.dk`, aldrig `@evil-aula.dk`.
  Uverificeret afsender kan ALDRIG udløse auto-oprettelse.
- **NU-anker = mailens Date-header** (konverteret til Europe/Copenhagen):
  "på fredag" i en tirsdags-mail er fredagen i mailens uge, også hvis mailen
  først behandles søndag. Midnats-mails i UTC rammer ellers forkert dag.
- **qwen2.5:7b JSON-drift:** én retry med fejlbesked, derefter fail-safe:
  hele mailen bliver ét `info`-item med confidence 0 — aldrig auto, aldrig
  tabt. Ollamas `format`-schema begrænser output strukturelt.
- **CPU-latens:** klassifikation kan tage minutter pr. mail. Overlap-låsen i
  main.py + `GMAIL_MAX_PER_POLL` forhindrer kø-eksplosion; første poll efter
  ferie tager bare flere ticks — det er OK.
- **Crash midt i LLM-kald:** mail-rækken står som `received` og genoptages
  næste poll. Findes der allerede items for mailen (crash midt i routing),
  oprettes der aldrig dubletter — mailen lukkes med de eksisterende items.
- **Dedupe-gaten** (samme dato ±1 dag, titel-lighed ≥ 0.75) fanger Aulas
  gensendte påmindelser, men ikke påmindelser >1 dag forskudt med omformuleret
  titel — de bliver forslag i stedet for dubletter, hvilket er acceptabelt.
- **Prompt-injection:** mail-indhold er DATA, aldrig kommandoer. Pipelinen kan
  arkitektonisk kun skrive forslag eller kalde gcal/vikunja-create med
  schema-validerede felter; Telegram-visning sker uden parse_mode; alt SQL er
  parametriseret; logs indeholder aldrig mail-body. Worst case ved perfekt
  injection: et fjollet forslag (🗑) eller en fjollet auto-event (Fortryd).

### Statusflow

`aula_messages.status`: `received` → `classified` (eller `failed`).
`aula_items.status`: `pending` → `approved`/`rejected`/`edited`/`expired`
(forslag), `auto_created` → evt. `undone` (auto), `briefed`/`notified` (info).

## Generel post-triage (Del 4)

Anden stream over samme postkasse: hele INBOX minus støj (Gmails
Promotions/Social-kategorier og `List-Unsubscribe`-header filtreres
deterministisk FØR LLM'en; mails med Aula-label ejes af Del 3-streamen).
Deler tabeller (`stream='inbox'`), poll-tick, TTL og knap-flow med Aula.

Forskelle fra Aula-pipelinen:

- **Ingen auto-sti overhovedet** — vilkårlige afsendere er fuldt utroede.
  Alt er highlights eller knap-forslag; godkendt forslag bliver en
  Vikunja-opgave med fristen som due date.
- **Admin-only overalt:** forslag/straks-beskeder går kun til
  `TELEGRAM_ADMIN_CHAT_ID`, post-digesten kl. 06:30 er en separat
  admin-besked (aldrig familie-briefen), og dashboard-blokken er gated som
  finance (aldrig i `/ambient`).
- **Egen history-cursor** (`gmail_history_id_inbox`) og eget lookback
  (`TRIAGE_LOOKBACK_DAYS`, default 3 — bevidst kort: første resync af en
  hel indbakke skal ikke koste hundredvis af LLM-kald).

Aktivering: `TRIAGE_ENABLED=true` i `.env` (kræver samme gmail.readonly-token
som Del 3; virker også uden Aula-label). Manuel test:

```bash
curl -X POST http://192.168.0.145:8300/api/post/poll
```

Støj (`status='skipped'`) registreres men klassificeres aldrig; `low` uden
handling droppes efter klassifikation. Kun `high`/frist-nære items giver
straks-besked; `normal` info samles i digesten (vises én gang).

## Ambient-flade på Wallpaper Engine (over LAN)

Ambient-visningen (`/ambient`) køres som live-wallpaper via Wallpaper Engine
ved at pege **direkte på caddy over LAN** — uden om Cloudflare-tunnelen.

### Hvorfor det er sikkert

PC og LXC 103 er på samme LAN. Cloudflare Access beskytter kun tunnel-vejen;
ambient-fladen er bevidst den ufølsomme visning (`/api/ambient` sender **aldrig**
finance eller post — det er derfor gatingen findes). Trafikken forlader aldrig
huset, så der er hverken login, tokens eller Cloudflare i den kritiske sti.

### Verifikation (bekræftet 2026-07-06)

Caddy lytter allerede på LAN-interfacet på **port 8080** — både siden og
data-stien er samme origin, så intet ekstra site-block var nødvendigt:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.0.145:8080/ambient      # 200 (Server: Caddy)
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.0.145:8080/api/ambient   # 200 (JSON, ingen økonomi)
```

Loader ambient kun via tunnelen (fx flyttet caddy-opsætning): tilføj et
site-block der lytter på LAN, og justér porten nedenfor.

### Opsætning i Wallpaper Engine

Wallpaper Engine loader en lokal fil, ikke en URL direkte, så et lille
wrapper-projekt loader LAN-URL'en i en fuldskærms-iframe (med genforbind-logik,
så en genstart af PC/server ikke efterlader en død skærm). Kilden ligger i
`ops/wallpaper-engine/lifehub-ambient/` og er kopieret til:

```
C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\projects\myprojects\lifehub-ambient\
```

Åbn Wallpaper Engine → wallpaperet **"LifeHub Ambient"** står under dine egne
(Installed) → vælg det → *Apply wallpaper*. Skifter LXC 103's IP eller
caddy-porten: ret `AMBIENT_URL` øverst i `index.html` (begge steder).

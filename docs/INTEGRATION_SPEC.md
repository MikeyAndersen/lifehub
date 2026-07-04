# INTEGRATION_SPEC — nova-madplan ↔ LifeHub

> **Formål:** Kontrakt-først design-spec. Claude Code må frit vælge/ændre implementering
> i begge repos, så længe kontrakterne i dette dokument overholdes.
> **Sprog:** Dokumentation dansk, kode/API/JSON-nøgler engelsk.

---

## 0. Guardrails (læses FØRST af Claude Code)

1. **Rør ALDRIG** LifeHubs dual-pass/review-kode: `brain/app/review.py`, tabellen
   `review_queue`, endpointet `/api/review/drain`. Ændringer i `agent/gpu_agent.py`
   må KUN være additive (ny config-post, ingen ændring af eksisterende adfærd).
2. Vikunja-update = fetch-merge-post (PUT erstatter hele task-objektet). Brug
   `filter_include_nulls=true` ved filtrerede GET-kald.
3. `.env`-ændringer på serveren kræver `docker compose down && up -d` (ikke restart).
4. Al service-til-service auth via Bearer-tokens i `.env` — ingen hardcoded secrets.
5. Ingen ændringer i LifeHubs eksisterende Telegram-intents før Fase 6.

---

## 1. Arkitekturbeslutninger (låst)

| # | Beslutning | Begrundelse |
|---|-----------|-------------|
| A1 | **nova-madplan er en selvstændig service** med egen FastAPI + SQLite, deployet som containere på LXC 103 | Spejler brain-stacken; to repos forbliver adskilte |
| A2 | **Madplan ejer:** retter (katalog), ugeplaner, historik, forslag | Domænedata bor hos domæne-appen |
| A3 | **LifeHub/brain ejer:** lager (Vikunja projekt 3), kalender, dashboard, Telegram, morgen-brief | Uændret ansvar |
| A4 | **Brain proxy'er lageret** via internt endpoint — madplan taler ALDRIG direkte med Vikunja | Ét integrationspunkt; Vikunja-finurligheder håndteres ét sted |
| A5 | **Madplan eksponerer ugeplanen** via REST; brain's feed-stub (`feeds/madplan.py`) poller og cacher | Feed-mønstret findes allerede som stub |
| A6 | **Forslags-motoren bor i madplan.** Hurtig sti: serverens 7b. Kvalitets-sti: PC'ens 32b via eget drain-endpoint (samme mønster som review, men SEPARAT kode/kø) | PC'en er ikke altid tændt; genbrug mønster, ikke kode |
| A7 | Services deler et **eksternt Docker-netværk `lifehub_net`** | Service-discovery via container-navn, ingen host-porte nødvendige internt |
| A8 | Stack for madplan: **FastAPI + SQLite (`/data/madplan.db`) + Astro/React frontend serveret af egen Caddy-route eller LifeHubs Caddy** | Konsistens med LifeHub; Claude Code vælger detaljer |

### Netværk

```yaml
# Begge compose-filer:
networks:
  lifehub_net:
    external: true
```
```bash
# Oprettes én gang på serveren:
docker network create lifehub_net
```
Interne URL'er: brain → `http://madplan-api:8000`, madplan → `http://brain:8000`.

---

## 2. Datakontrakter (JSON)

### 2.1 Dish (ret)

```json
{
  "id": 17,
  "name": "Kylling i karry",
  "tags": ["hverdag", "kylling"],
  "recurring_weekly": false,
  "ingredients": [
    {"name": "kyllingebryst", "qty": 500, "unit": "g"},
    {"name": "ris", "qty": 4, "unit": "dl"}
  ],
  "last_made": "2026-06-28",
  "active": true
}
```
- `recurring_weekly: true` = fast ugentlig ret, undtaget fra 14-dages-reglen.
- `ingredients[].name` matches mod lager med normaliseret lowercase + fuzzy (se 4.2).

### 2.2 WeekPlan

```json
{
  "week_start": "2026-07-06",
  "days": [
    {
      "date": "2026-07-06",
      "weekday": "mandag",
      "dish_id": 17,
      "dish_name": "Kylling i karry",
      "status": "planned",
      "note": null
    }
  ],
  "updated_at": "2026-07-04T18:22:00+02:00"
}
```
- `status`: `planned` | `cooked` | `skipped` | `empty` (dish_id null ved empty).
- Kun aftensmad i v1. Frokost/andet er out of scope.
- Når en dag markeres `cooked` → skriv til historik + opdater `last_made`.

### 2.3 InventoryItem (fra brain)

```json
{
  "name": "kyllingebryst",
  "raw_title": "Kyllingebryst 500g",
  "done": false,
  "vikunja_task_id": 412,
  "updated_at": "2026-07-04T12:01:00+02:00"
}
```
- Semantik: Vikunja "Indkøb" (projekt 3) fungerer som lager. `done=false` = på
  listen (skal købes / haves ikke nødvendigvis). **v1-tolkning:** åbne tasks =
  "kommer ind i huset snart", afsluttede tasks seneste 7 dage = "er på lager".
  Brain leverer begge mængder; madplan afgør vægtning. (Denne semantik kan
  justeres — feltet `bucket`: `"open"` | `"recently_done"`.)

### 2.4 SuggestionSet

```json
{
  "week_start": "2026-07-13",
  "generated_by": "qwen2.5:7b-instruct",
  "quality": "fast",
  "inventory_hash": "sha256:ab12…",
  "suggestions": [
    {
      "date": "2026-07-13",
      "dish_id": 3,
      "dish_name": "Spaghetti bolognese",
      "reason": "Hakket oksekød og pasta på lager; sidst lavet for 19 dage siden",
      "confidence": 0.82
    }
  ],
  "updated_at": "2026-07-04T18:25:00+02:00"
}
```
- `quality`: `fast` (7b) | `reviewed` (32b har opgraderet sættet).
- 32b-pass må erstatte/omrokere forslag, men menneske-vinder-regel gælder:
  dage brugeren allerede har accepteret/planlagt røres ikke.

---

## 3. API-kontrakter

### 3.1 nova-madplan eksponerer

| Metode | Path | Auth | Beskrivelse |
|--------|------|------|-------------|
| GET | `/api/weekplan/current` | `LIFEHUB_API_TOKEN` | Indeværende uges plan (2.2) |
| GET | `/api/weekplan?start=YYYY-MM-DD` | samme | Vilkårlig uge |
| GET | `/api/suggestions/current` | samme | Nyeste SuggestionSet (2.4) for næste uge |
| POST | `/api/suggestions/refresh` | samme | Trig recompute (7b) — returnerer 202 |
| POST | `/api/suggestions/accept` | samme | Body: `{"date": "...", "dish_id": n}` → skriver ind i ugeplan |
| POST | `/api/drain` | `MADPLAN_DRAIN_TOKEN` | 32b-agenten dræner forslags-kø (se 5) |
| GET | `/api/dishes`, CRUD | samme/UI | Katalog-vedligehold (primært til egen frontend) |
| GET | `/healthz` | ingen | Liveness |

### 3.2 LifeHub/brain eksponerer (NYT)

| Metode | Path | Auth | Beskrivelse |
|--------|------|------|-------------|
| GET | `/api/internal/inventory` | `INTERNAL_API_TOKEN` | Liste af InventoryItem (2.3), begge buckets. Håndterer selv `filter_include_nulls`, paginering, normalisering |

### 3.3 LifeHub/brain forbruger (feed)

- `feeds/madplan.py` implementeres oven på eksisterende stub:
  - Poll `GET madplan-api:8000/api/weekplan/current` hvert 10. min + ved dashboard-load
    hvis cache > 10 min gammel.
  - Cache i brains SQLite (`feed_cache`-mønster hvis det findes, ellers simpel tabel).
  - Fejltolerance: madplan nede → vis seneste cache med `stale: true`, aldrig crash.
- **Dashboard:** ugeplan-kort i både interaktivt og ambient layout (7 dage, i dag
  fremhævet). Ambient: kun i dag + i morgen.
- **Morgen-brief (06:30):** én linje: *"Aftensmad i dag: Kylling i karry"* (eller
  *"Ingen madplan for i dag"* — udelad linjen helt hvis hele ugen er tom).

---

## 4. Forslags-motor (bor i nova-madplan)

### 4.1 Triggere for recompute (7b, fast)

1. Inventory-poll: madplan poller `brain/api/internal/inventory` hvert 15. min;
   recompute KUN hvis `inventory_hash` er ændret.
2. Manuel: `POST /api/suggestions/refresh` (knap i madplan-UI).
3. Natligt cron-job kl. 03:00 (fanger `last_made`-drift ved ugeskifte).
4. En dag markeres `cooked`/`skipped` (historik ændret).

### 4.2 Algoritme (deterministisk pre-filter + LLM-ranking)

```
kandidater = aktive retter
  MINUS retter med last_made < 14 dage siden (medmindre recurring_weekly)
score-input pr. kandidat:
  - ingrediens-dækning mod lager (normaliseret navn, fuzzy match ≥ 0.85 ratio,
    "recently_done"-bucket vægter 1.0, "open" vægter 0.6)
  - dage siden last_made (ældre = bedre)
  - recurring_weekly → garanteret plads på sin sædvanlige ugedag hvis muligt
LLM-kald (7b): få kandidatliste + lager + historik som kompakt JSON,
  returnér KUN JSON (SuggestionSet.suggestions) — 7 dage, begrundelse pr. dag.
Validering: dish_id skal findes i kandidatlisten; ellers drop + refill deterministisk.
```

- Prompt-budget: hold input < ~2.500 tokens (7b på CPU, ~20s — acceptabelt async).
- Resultat gemmes som nyt SuggestionSet med `quality: "fast"` + kø-post til 32b.

### 4.3 14-dages-reglen (præcisering)

- Hård udelukkelse < 14 dage, MEDMINDRE `recurring_weekly` ELLER kandidatmængden
  ellers falder under 7 → så blødes op til < 7 dage med lavere confidence.

---

## 5. 32b kvalitets-pass (drain-mønster — SEPARAT fra review)

- Egen SQLite-tabel i `madplan.db`: `suggest_queue(id, week_start, payload_json,
  status pending|done|expired, created_at, done_at)` — idempotent på `week_start`
  (nyeste pending pr. uge vinder, ældre markeres expired). Hård grænse: 7 dage.
- `POST /api/drain` (Bearer `MADPLAN_DRAIN_TOKEN`):
  1. Agent kalder med `{"ollama_url": "http://192.168.0.162:11434"}` (som review-drain).
  2. Madplan tager ældste pending, kalder 32b (`STRONG_OLLAMA_MODEL`), genererer
     forbedret SuggestionSet (`quality: "reviewed"`).
  3. Menneske-vinder: dage med status `planned`/`cooked` i ugeplanen overskrives ikke.
- **Agent-ændring (ADDITIV):** `gpu_agent.py` udvides til at læse en liste af
  drain-URLs fra sin config (eksisterende review-URL + ny madplan-URL) og kalde dem
  sekventielt. Eksisterende kald/flow/idle-tjek uændret. Fallback hvis config-listen
  mangler: nuværende adfærd.
- Falder 32b-kaldet (PC slukket/timeout 120s) → kø-posten forbliver pending. 7b-sættet
  er allerede live, så intet er blokeret.

---

## 6. Miljøvariabler

### nova-madplan `.env`
```bash
DATABASE_PATH=/data/madplan.db
BRAIN_URL=http://brain:8000
INTERNAL_API_TOKEN=<samme som brain>          # til inventory-kald mod brain
LIFEHUB_API_TOKEN=<secret>                    # brain → madplan auth
MADPLAN_DRAIN_TOKEN=<secret>                  # agent → madplan drain
OLLAMA_URL=http://ollama:11434                # serverens 7b (delt container)
OLLAMA_MODEL=qwen2.5:7b-instruct
STRONG_OLLAMA_MODEL=qwen2.5:32b-instruct
INVENTORY_POLL_MINUTES=15
```

### LifeHub `.env` (tilføjelser)
```bash
MADPLAN_URL=http://madplan-api:8000
LIFEHUB_API_TOKEN=<samme secret som ovenfor>  # brain → madplan
INTERNAL_API_TOKEN=<secret>                   # madplan → brain inventory
```

### Agent-config (Windows, additivt)
```json
{ "drain_urls": [
    "https://<eksisterende review-drain>",
    "https://<madplan-drain, samme tunnel/Access-mønster>"
] }
```

> Ollama-containeren i LifeHub-compose deles (A7-netværket gør den nåbar som
> `http://ollama:11434`). Ingen ny Ollama-instans.

---

## 7. Faseplan (Claude Code eksekverer i rækkefølge, én fase = én leverance)

| Fase | Repo(er) | Indhold | Accept-kriterium |
|------|----------|---------|------------------|
| 1 | nova-madplan | Ny stack: FastAPI-skelet, SQLite-schema (dishes, weekplan, history, suggest_queue), compose på `lifehub_net`, `/healthz`, dish-CRUD, ugeplan-CRUD, seed-migrering af eksisterende retter/data fra gammel stack | `curl madplan-api:8000/api/weekplan/current` returnerer gyldig 2.2-JSON |
| 2 | lifehub | `feeds/madplan.py` (poll+cache+stale), dashboard-ugeplankort (begge layouts), morgen-brief-linje | Ugeplan synlig på dashboard; brief viser dagens ret; madplan-container stoppet → dashboard viser stale cache uden fejl |
| 3 | lifehub | `GET /api/internal/inventory` (begge buckets, normalisering, Vikunja-regler fra §0) | JSON matcher 2.3; åbne + nyligt afsluttede tasks fra projekt 3 kommer med |
| 4 | nova-madplan | Forslags-motor 7b: pre-filter, LLM-ranking, triggere (poll/manuel/cron/cooked), `/api/suggestions/*` | Nyt SuggestionSet genereres < 2 min efter lagerændring; 14-dages-regel verificerbar; accept skriver til ugeplan |
| 5 | begge + agent | `suggest_queue` + `/api/drain`; additiv agent-config med URL-liste | PC tændt → sæt opgraderes til `quality:"reviewed"`; PC slukket → 7b-sæt forbliver aktivt; review-flowet beviseligt uændret |
| 6 (valgfri) | lifehub | Telegram-intents: "hvad skal vi have i aften?", "accepter madplanen for næste uge" → brain router til madplan-API | Svar i Telegram < 30s |

---

## 8. Antagelser (ret hvis forkert, ellers gælder de)

1. Kun aftensmad planlægges (v1).
2. Ugen starter mandag; forslag genereres altid for **næste** uge.
3. Lager-semantik som beskrevet i 2.3 (buckets) er acceptabel som v1-approksimation.
4. Madplan-frontend (til redigering/accept) er intern på LAN; eksponering via
   Cloudflare Tunnel er en senere beslutning.
5. Eksisterende data i gamle nova-madplan kan eksporteres/migreres i Fase 1
   (Claude Code afdækker gammel struktur og skriver engangs-migrering).

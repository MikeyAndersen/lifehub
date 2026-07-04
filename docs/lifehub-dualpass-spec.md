# LifeHub — Design Spec: Dual-Pass Parsing + GPU Boot-Agent

## Kontekst
LifeHub er en selvhostet familie-assistent (FastAPI "brain" + Astro dashboard) på en
Proxmox-server. Beskeder kommer via Telegram-webhook, parses af en lokal Ollama-model
(`qwen2.5:7b-instruct`, CPU) til struktureret JSON, og oprettes som Google Calendar-events
/ Vikunja-opgaver / indkøb / udgifter.

Brugeren prioriterer **kvalitet og præcision over minut-til-minut aktualitet**, men vil
ikke miste tidskritiske beskeder når gaming-PC'en er slukket. PC'en har en kraftig GPU der
kan køre en større model lynhurtigt, men er ikke altid tændt og må ikke forstyrre gaming.

Løsningen har to dele:
1. **Dual-pass parsing** (server) — parse altid lokalt straks, kvalitetssikr bagefter med
   den stærke model når PC'en er online.
2. **GPU boot-agent** (Windows, på gaming-PC'en) — kører den stærke model kortvarigt ved
   boot for at tømme kvalitetskøen, og trækker sig igen.

Begge dele er **opt-in**. Uden konfiguration opfører systemet sig præcis som i dag.

---

## DEL 1 — Dual-pass parsing (serverkode)

### Pass 1 — altid, lokalt, straks
Hver besked parses med det samme af den lokale 7B-model, og handlingen udføres øjeblikkeligt
(event/opgave oprettes). Sikrer at tidskritiske ting ("møde i morgen kl. 8") altid rammer
kalenderen til tiden. Uændret fra nuværende adfærd, bortset fra at resultatet nu også lægges
i en kvalitetskø.

### Pass 2 — kvalitetssikring når PC'en er online
Alle Pass-1-resultater lægges i kø. Når den stærke models Ollama er tilgængelig (PC'en
tændt + boot-agenten kører), køres samme besked gennem den store model. Afviger tolkningen
(dato, titel, type, beløb…), **opdateres den allerede oprettede handling** — den store
models tolkning bliver source of truth. Er tolkningen ens, sker intet. Brugeren får én
samlet Telegram-besked om eventuelle rettelser.

### Konfiguration (.env)
- `STRONG_OLLAMA_URL` — gaming-PC'ens Ollama (fx `http://192.168.0.50:11434`). Tom = Pass 2 slået fra.
- `STRONG_OLLAMA_MODEL` — modelnavn på PC'en. **Hardware: AMD RX 7900 XTX (24 GB VRAM) + 64 GB RAM.**
  Anbefalet stærk model: `qwen2.5:32b-instruct` (fylder ~20 GB i 4-bit, passer i VRAM, fuld
  GPU-fart, stort kvalitetsspring over den lokale 7B til dansk). Kan evt. gå højere (70B) via
  system-RAM-offload hvis man accepterer lavere hastighed — men 32B er den anbefalede søde plet.
- `REVIEW_HARD_MAX_AGE_DAYS` — hård grænse: kø-elementer ældre end dette slettes helt uden
  kvalitetssikring (default 7). Sikkerhedsventil så køen aldrig vokser i det uendelige
  (fx under ferie). PC'en tændes normalt inden for 72t, så 7 dage er rigelig margin.
- Eksisterende lokale `OLLAMA_URL` / `OLLAMA_MODEL` uændret.

### Relevans-model (vigtigt — erstatter simpelt tidsfilter)
Kvalitetssikring handler om at rette handlinger der *stadig betyder noget*. Relevans afgøres
af handlingens egen tilstand, IKKE af hvor gammelt kø-elementet er. For hvert `pending`-element:
1. **Hård grænse først:** er elementet ældre end `REVIEW_HARD_MAX_AGE_DAYS` (7)? → `mark_review(id,"expired")`, slet, spring over. (Strandet, fx pga. ferie.)
2. **Findes handlingen stadig, og er den relevant?**
   - Opgave (Vikunja): slå den op via `created_ref`. Findes den ikke længere, eller er den
     markeret **done**? → irrelevant → `mark_review(id,"expired")`, ryd. (Du har allerede
     krydset den af — intet at rette.)
   - Event (Calendar): slå det op. Ligger dets **sluttidspunkt i fortiden**? → overstået →
     `mark_review(id,"expired")`, ryd.
   - Ellers (opgave stadig åben / event i fremtiden): fortsæt til kvalitetssikring — UANSET
     hvor gammelt kø-elementet er (så længe under 7-dages grænsen).
3. **"Forældet" afgøres sammen med den stærke model, ikke som blindt forhåndsfilter:** hvis
   den lokale 7B fejlparsede en dato så et event ser overstået ud, men den stærke model læser
   det som en fremtidig dato, skal datoen RETTES — ikke afvises. Så fortids-tjekket i punkt 2
   bruger den eksisterende oprettede dato; hvis den stærke model er uenig og placerer det i
   fremtiden, opdateres eventet frem for at blive ryddet.
4. Efter en stærk-model-gennemgang: `mark_review(id,"done")` — betyder "kvalitetssikret én
   gang", så fremtidige events ikke re-tjekkes ved hvert boot. (`done` ≠ handling overstået.)

### Komponenter

**1. Kø-tabel (`store.py`)** — ny tabel `review_queue`:
- `id` (uuid), `source_text`, `chat_id`, `pass1_parsed` (JSON),
- `received_at` (ISO, **beskedens oprindelige modtagelsestidspunkt** — bruges som "NU"-anker
  ved genparsing, se KRITISK note under llm.py),
- `created_ref` (JSON — reference(r) til det oprettede så det kan opdateres/slettes. Skal
  kunne være en **liste**, da fx indkøb opretter flere opgaver. Eksempler:
  `[{"kind":"event","calendar_id":..,"event_id":..}]`,
  `[{"kind":"task","project_id":..,"task_id":..}, ...]`,
  `[{"kind":"expense","row_id":..}]`),
- `created_at` (epoch), `status` (`pending`|`done`|`expired`).
- Funktioner: `enqueue_review(...)`, `list_pending_reviews(limit)`, `mark_review(id, status)`.

**2. Webhook-handler (`telegram.py`)** — behold øjeblikkelig udførelse, men:
- Refaktorér `_execute` til at returnere `(besked, created_ref)`.
- Hvis `STRONG_OLLAMA_URL` er sat: kald `store.enqueue_review(...)` efter udførelse.

**3. Dual-model kald (`llm.py`)**
- Generalisér `_chat` / `parse_message` til valgfri `base_url` + `model` (default = lokal),
  så samme kode kan køre mod både lokal og stærk Ollama.
- **KRITISK — "NU"-anker ved genparsing:** `parse_message` skal have en valgfri `now`-parameter.
  Prompten fortæller modellen "NU er \<tidspunkt\>" til at opløse relative udtryk ("på torsdag",
  "i morgen"). Ved Pass 2 SKAL `now` sættes til kø-elementets `received_at` — IKKE aktuel tid.
  Ellers vil en besked som "tandlæge på torsdag", kvalitetssikret 3 dage senere, blive opløst
  til en ANDEN torsdag, og kvalitetssikringen ville "rette" korrekte events til forkerte datoer.
- Tilføj `is_online(base_url)`: kort GET mod `{base_url}/api/tags`, timeout 2-3s.
- **Vigtigt:** kald mod den stærke model sætter `keep_alive: "0"` i request-body, så PC'ens
  GPU frigiver modellen umiddelbart efter hvert kald (ingen resident VRAM-brug).

**4. Kvalitetssikrings-endpoint (nyt `review.py` + route i `main.py`)**
I stedet for at serveren poller PC'en, **kalder boot-agenten serveren** når den er klar
(se Del 2). Eksponér en beskyttet route, fx `POST /api/review/drain`, der:
1. Hvis `STRONG_OLLAMA_URL` tom → returnér straks `{"processed":0}`.
2. Tjek `is_online(STRONG_OLLAMA_URL)`; hvis offline → returnér.
3. Hent `list_pending_reviews(limit=10)` — **batch på maks ~10 pr. kald**, så HTTP-kaldet
   forbliver kort (agenten looper alligevel til `processed` er 0). For hver: anvend
   **relevans-modellen** (se afsnittet ovenfor): tjek hård 7-dages grænse → tjek om
   handlingen stadig findes og er relevant (opgave åben / event i fremtiden / udgift findes;
   noter oprettes som opgaver og følger opgave-reglen) → ellers kvalitetssikr:
   a. **Bruger-redigering vinder over begge modeller:** hent handlingens AKTUELLE tilstand
      og sammenlign med `pass1_parsed`. Matcher den ikke længere (brugeren har manuelt
      flyttet/omdøbt/ændret den), så spring korrektionen over og `mark_review(id,"done")`
      — et menneskes rettelse må aldrig overskrives af kvalitetstjekket.
   b. Kør `parse_message(source_text, base_url=STRONG_OLLAMA_URL, model=STRONG_OLLAMA_MODEL,
      now=received_at)` — bemærk `now`-ankeret (se llm.py).
   c. Sammenlign med `pass1_parsed` på betydende felter (intent, title, start, end, due,
      all_day, amount_dkk, items), normaliseret (trim, ens datoformat).
   d. Hvis forskellig: opdatér via `created_ref` (event → Calendar update; task/shopping →
      Vikunja update; udgift → opdatér udgiftsrækken i SQLite; skifter intent type → slet
      gammel + opret ny, og skriv den NYE ref til kø-rækken FØR sletning af den gamle, så et
      crash midt i ikke kan give dubletter ved genkørsel). Saml kort beskrivelse.
   e. `mark_review(id,"done")`.
4. Én samlet Telegram-besked pr. chat_id hvis noget blev rettet ("🔄 Kvalitetstjek: rettede N ting: …"). Intet ændret = ingen besked.
5. Returnér `{"processed":N,"corrected":M}` så agenten ved om der er mere.

**5. Calendar/Vikunja opdatering (`gcal.py`, `vikunja.py`)**
- `update_event(created_ref, new_parsed)`, `delete_event(created_ref)` i gcal.py.
- `update_task(...)`, `delete_task(...)` i vikunja.py.
- `create_event`/`create_task` skal returnere nok til at bygge `created_ref`.

---

## DEL 2 — GPU boot-agent (Windows, på gaming-PC'en)

Et selvstændigt lille Python-script (`gpu_agent.py`) der lever på gaming-PC'en, adskilt fra
serverkoden. Leveres i repoet under fx `agent/` med sin egen README.

### Adfærd (bevidst simpel)
1. **Starter ved boot** (via Windows Task Scheduler, trigger "At log on").
2. Ved start: mål GPU-forbrug. **Bemærk: maskinen har et AMD Radeon RX 7900 XTX på Windows —
   `rocm-smi` og `nvidia-smi` findes IKKE her** (rocm-smi er et Linux-værktøj). Brug i stedet
   Windows' egne performance counters, fx
   `typeperf "\GPU Engine(*)\Utilization Percentage" -sc 1` (eller PowerShell
   `Get-Counter`) og summér/max engine-utilization. Hvis under **30%** → fortsæt. Ellers
   vent i korte intervaller til det har været under 30% i et par minutter, så fortsæt.
   **Fail-open:** kan GPU-forbruget ikke måles (counter mangler), så log en advarsel og
   fortsæt alligevel — måling er en høflighed, ikke en hård afhængighed. Gør måle-funktionen
   isoleret så den nemt kan udskiftes ved hardwareskift.
3. Sørg for at PC'ens Ollama kører og lytter på LAN (`OLLAMA_HOST=0.0.0.0`). Start den om nødvendigt.
4. Kald serverens `POST /api/review/drain` gentagne gange indtil `processed` er 0
   (køen tom) — ELLER indtil der er gået **10 minutter** siden start, hvad end kommer først.
5. Når køen er tom eller tidsboksen udløber: bed Ollama aflæsse modellen (kald med
   `keep_alive:"0"`, eller `ollama stop <model>`), og afslut agenten. Færdig for denne boot.
6. **Ingen periodisk genkørsel** — kun ved boot. Beskeder der kommer mens PC'en er tændt
   men agenten er afsluttet, fanges ved næste boot (eller manuel CLI-kørsel), og serverens
   relevans-model + 7-dages hårde grænse sikrer at intet strander for evigt.

### Konfiguration (agentens egen .env eller config)
- `LIFEHUB_SERVER_URL` — serverens adresse. **Anbefal LAN-adressen** (fx
  `http://192.168.0.145:8080`): den offentlige `https://lifehub.nova-tech.dk` ligger bag
  Cloudflare Access, som ville svare 302/login på `/api/review/drain` medmindre der laves
  en Access-bypass eller service-token for den sti. På LAN er bearer-tokenet beskyttelsen.
- `REVIEW_DRAIN_TOKEN` — delt hemmelighed der sendes som header, så kun agenten kan kalde
  `/api/review/drain` (serveren tjekker den).
- `GPU_START_THRESHOLD` = 30 (%), `TIMEBOX_MINUTES` = 10 (default tidsboks), `OLLAMA_MODEL` = den stærke model.

### Manuel CLI-kørsel
Samme `gpu_agent.py` skal kunne køres manuelt fra kommandolinjen, ikke kun via Task
Scheduler. Argumenter:
- `python gpu_agent.py` — kører default: 30%-tjek, 10-minutters tidsboks (samme som boot).
- `python gpu_agent.py --minutes 25` — kør i 25 min i stedet for default 10.
- `python gpu_agent.py --now` — spring 30%-GPU-tjekket over og start med det samme
  (til når man selv ved at PC'en er ledig og bare vil have køen tømt nu).
- `python gpu_agent.py --minutes 30 --now` — kombinerbart.
- `python gpu_agent.py --once` — kør præcis én drain-runde og afslut (uden tidsboks-loop),
  nyttigt til hurtig test.
Task Scheduler-triggeren ved boot kalder simpelthen `python gpu_agent.py` uden argumenter.
En bat-fil / genvej (`drain.bat`) der kører `python gpu_agent.py --now` gør det nemt at
starte manuelt med ét klik. Dokumentér begge i agentens README.

### Beskyttelse af drain-endpointet
`/api/review/drain` må ikke være åben. Enten en simpel bearer-token (`REVIEW_DRAIN_TOKEN`)
som agenten sender og serveren kræver, eller — hvis det går via Cloudflare — en Access
service-token. Vælg bearer-token for enkelhed på LAN.

---

## Vigtige krav og faldgruber
- **Bagudkompatibelt:** `STRONG_OLLAMA_URL` tom → ingen kø, ingen ekstra kald, som i dag.
- **"NU"-anker:** genparsing bruger ALTID `received_at` som reference-tidspunkt — aldrig
  aktuel tid (ellers flytter relative datoer sig).
- **Mennesket vinder:** manuelt redigerede handlinger korrigeres aldrig (sammenlign live-tilstand
  mod `pass1_parsed` før rettelse).
- **Idempotens:** markér `done` FØRST efter opdatering er lykkedes; ved intent-type-skift
  skrives ny ref før gammel slettes, så genkørsel efter crash ikke giver dubletter.
- **PC skal nås:** dokumentér `OLLAMA_HOST=0.0.0.0` på PC'en, og at serveren kan route til PC'ens IP.
- **Én notifikation pr. drain pr. chat**, ikke én pr. rettelse.
- **Tidszone:** al datosammenligning i Europe/Copenhagen.
- **Rør ikke** ved den lokale models valg — forbliver `qwen2.5:7b-instruct`.
- Den stærke models kald bruger altid `keep_alive:"0"` så GPU'en frigives straks.

## Test
- `STRONG_OLLAMA_URL` tom: send besked → som i dag, ingen kø-aktivitet.
- PC offline: besked parses lokalt, oprettes, ligger `pending` i kø.
- Agent kører (simulér ved at kalde `/api/review/drain` manuelt med token): kø tømmes,
  evt. korrektion + samlet notifikation.
- **"På torsdag"-besked kvalitetssikret 3 dage senere → opløses til SAMME torsdag som Pass 1
  (received_at-ankeret virker).**
- **Event manuelt flyttet af brugeren efter Pass 1 → kvalitetstjek rører det ikke, markerer done.**
- Opgave allerede markeret done før tjek → element ryddes som `expired`, ingen rettelse.
- Event hvis sluttid er i fortiden → ryddes som `expired`.
- Åbent, fremtidigt event 3 dage gammelt → kvalitetssikres stadig (relevans, ikke alder).
- Element ældre end 7 dage → slettes som `expired` uden tjek.
- Kø med 25 elementer → tømmes over flere drain-kald (batch á 10), agenten looper.
- `python -m py_compile brain/app/*.py` skal passere.

Arbejd i små, forklarede commits. Bevar/opdatér konsekvent funktionssignaturer der importeres
andre steder. Læg boot-agenten i `agent/` med egen README (inkl. Task Scheduler-opsætning).
Giv til sidst den præcise `git push`-kommando.

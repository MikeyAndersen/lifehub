# LifeHub Ambient — stor opgradering: Implementeringsplan

> **For agentic workers:** Eksekveres inline i denne session (bruger-instruks: kør hele vejen igennem på main, commit i logiske steps).

**Goal:** Minimalistisk space-opgradering af dashboard + ny /ambient/orbit-side med reelle systemstats fra brain.

**Architecture:** Frontend er Astro + React (dashboard/). Backend er FastAPI (brain/app). Alle effekter trækker fra et nyt fælles CSS-variabel-system i global.css. Stats aggregeres i nyt modul brain/app/ambient_stats.py fra eksisterende SQLite-tabeller + ny letvægts sys_events-log; tal der ikke kan udledes historisk logges KUN fremadrettet og vises som "indsamler data…" indtil da.

**Tech Stack:** Astro 5, React 18, ren CSS/canvas (ingen libraries), FastAPI, sqlite3.

## Global Constraints (design-princip)

- Nebula-opacity max 0.10–0.15; glow-opacity max 0.25; store blur-spredninger.
- Afdæmpet palette (støvet cyan/violet/rosa/sand/grøn), aldrig neon. Én accent-detalje pr. card.
- Animation: breathing 6–10s, drift 45–90s; intet blinker/roterer hurtigt.
- prefers-reduced-motion respekteres overalt (global.css dræber CSS-animationer; canvas-loops fryser som i Wings.jsx).
- rAF-loops pauser ved document.hidden (mønster fra Wings.jsx). Max 80 partikler.
- Opfind ALDRIG tal i stats — null → "indsamler data…".

---

### Task 1 (DEL 4, først): Kalender-overlap-fix
**Files:** Modify `dashboard/src/components/widgets/Kalender.jsx`, `dashboard/src/styles/global.css`, `brain/app/gcal.py` (additivt `end`-felt i event-feedet).
- Overlap-algoritme pr. dag-gruppe: kluster tidsatte events hvis [start, end∥start+60min) overlapper; kluster med N>1 renderes som N kolonner (width 100/N%, left = idx*100/N%); solo-events fuld bredde.
- Titler: ellipsis + line-clamp:2, min-height ≥ 1 linje, hover-tooltip (title-attribut + custom .ev-tip).
- Commit: `Fix(DEL 4): kalender-overlap i kolonner + ellipsis/tooltip`.

### Task 2 (DEL 1 + DEL 2 statisk): Ambient design system + glas-cards
**Files:** Modify `dashboard/src/styles/global.css`, `dashboard/src/components/widgets/Card.jsx`, alle widgets (accent-prop).
- :root-vars: `--acc-calendar/tasks/mail/weather/system` (afdæmpede), `--glow-op:0.2` (max .25), `--blur-card:16px`, `--blur-nebula:130px`, `--t-breath:8s`, `--t-drift:70s`, `--t-countup:800ms`.
- .card: backdrop-filter blur(16px), rgba-baggrund, 1px semi-transparent border, inset-highlight top, blød løftende skygge, én border-glow i `--card-acc`.
- Kalender-cardet (vigtigst) får statisk svag gradient-border (`.card--primary`, dobbelt-gradient border-box, ingen rotation).
- Commit: `DEL 1+2: ambient design system, glassmorphism og accent-glow pr. card`.

### Task 3 (DEL 2 bevægelse): Backdrop (nebula + partikler) + useCountUp + opdaterings-lysskifte
**Files:** Create `dashboard/src/components/Backdrop.jsx`, `dashboard/src/lib/useCountUp.js`; modify `Dashboard.jsx`, `Card.jsx`, `Hero.jsx`, `Oekonomi.jsx`, `Aula.jsx`, `Post.jsx`, `global.css`.
- Backdrop: 3 z-lag — nebula-divs (radial-gradients, blur ≥120px, opacity ≤0.15, CSS-drift 60–90s, svag parallax-forskel mellem lag), canvas-partikler (max 80, 3 dybdelag, opacity ≤0.4, sinus-twinkle, rAF med hidden/reduced-motion-pause à la Wings), cards ovenpå.
- `useCountUp(value, {duration:800})`: rAF ease-out; reduced-motion → hop direkte.
- Card: `pulseKey`-prop; ved ændring tilføjes `.card--updated` i ~1.4s (blødt opacity-lysskifte, ikke flash).
- Commit: `DEL 2: nebula/partikel-backdrop, useCountUp og blødt data-lysskifte`.

### Task 4 (DEL 3): Time-of-day paletter + vejr-planet
**Files:** Create `dashboard/src/lib/daycycle.js`, `dashboard/src/components/Planet.jsx`; modify `Dashboard.jsx`, `global.css`.
- 4 paletter (morgen/dag/aften/nat) som RGB-keyframes; blød interpolation efter klokken (opdateres hvert minut) → CSS-vars `--tod-*` på :root. Backdrop/nebula/planet trækker fra dem.
- Planet: layered radial-gradients (SVG/CSS), terminator-overlay der vandrer med døgnet; vejr-tilstande fra `data.weather.code/wind_ms`: klar / skylag (blurede ellipser, drift-hastighed øges let ved blæst) / svage regn-streaks + køligere tone / nat med svage bylys. Placeres øverst på hovedskærmen.
- Commit: `DEL 3: time-of-day theming og vejr-planet`.

### Task 5 (DEL 5 backend): sys_events-log + /api/ambient/stats + /api/ambient/events
**Files:** Modify `brain/app/store.py` (tabel sys_events, log_event/recent_events/count-helpers, kv `stats_since`), `brain/app/review.py` (status 'corrected' + log pr. pass2-outcome), `brain/app/telegram.py` (log 'prompt'), `brain/app/vikunja.py` (log 'vikunja_write' i create/update/delete/set_done), `brain/app/main.py` (endpoints); Create `brain/app/ambient_stats.py`.
- Udledes historisk (ægte tal): pass1-total = review_queue rows; pass2-total = rows status≠'pending'; triage i dag = aula_messages stream='inbox' received_at≥i dag.
- Kun fremadrettet (sys_events, ellers null): prompts (i dag + total siden `stats_since`), korrektionsrate = corrected/(corrected+done) af pass2-events, vikunja-writes i dag, travleste time.
- Aggregering caches i proces 45s. /api/ambient/events: seneste events med `since_id`-param (polling).
- Ingen private payloads i events (ambient er delt flade): kun kind + generisk label.
- Verifikation: py_compile + scriptet røgtest af aggregering mod temp-DB.
- Commit: `DEL 5 backend: sys_events, /api/ambient/stats og /api/ambient/events`.

### Task 6 (DEL 5 frontend): /ambient/orbit
**Files:** Create `dashboard/src/pages/ambient/orbit.astro`, `dashboard/src/components/orbit/OrbitScreen.jsx` (+ små underkomponenter i samme mappe), CSS i global.css (egen sektion); modify `dashboard/src/lib/api.js` (fetchAmbientStats/fetchAmbientEvents).
- 1920×1080-stage skaleret som Ambient.jsx. Central orb (layered gradients + blur, breathing 8s), 2–3 tynde ringe, ring-gauge (SVG stroke-dasharray) for korrektionsrate, to måner skaleret efter 7b/32b-andel, svævende glas-paneler med CountUp-stats, event-partikler der kredser ind og absorberes (opacity-ease 1.5s) + fadende label, stort ur + næste kalender-event, cursor skjules efter 3s, ingen scrollbars, time-of-day-palette gælder.
- Poll: stats 45s, events 10s, kalender via fetchDashboard(true) 60s.
- Commit: `DEL 5: /ambient/orbit mission control`.

### Task 7: Lint/build + SUMMARY.md
- `npm run build` i dashboard/ (ret alle fejl), py_compile af hele brain/app.
- Skriv `dashboard/src/components/ambient/SUMMARY.md` (ambient-mappen): hvad er lavet, nye endpoints, hvilke stats mangler data-logging.
- Commit: `Ambient-opgradering: build-fixes og SUMMARY`.

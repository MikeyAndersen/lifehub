# LifeHub Ambient — opgradering (juli 2026)

Minimalistisk space-opgradering af dashboardet + ny orbit-skærm. Stilen er
roligt observatorium: nebula ≤0.15 opacity, glows ≤0.25, langsomme timings
(breathing 6–10s, drift 45–90s). Alt respekterer `prefers-reduced-motion`
(global CSS-regel + frosne canvas-loops) og pauser ved `document.hidden`.

## Hvad er lavet

**DEL 4 — kalender-fix (først):** Overlappende tidsatte events klustres pr.
dag og fordeles grådigt i N kolonner (100/N % bredde, kolonneindeks som
offset); solo-events beholder fuld bredde. Events uden sluttid antages
60 min — `gcal.py` sender nu et additivt `end`-felt. Titler har
line-clamp/ellipsis, chips min-height og hover-tooltip.
(`widgets/Kalender.jsx`)

**DEL 1 — design system:** Fælles CSS-vars i `global.css`: accenter pr.
card-type (støvet cyan=kalender, dæmpet violet=opgaver, dæmpet rosa=post/
aula, varm sand=vejr/hero, dæmpet grøn=system/øvrige), `--glow-op` (0.20,
max 0.25), blur-niveauer og animation-timings. Alle effekter trækker herfra.

**DEL 2 — dybde og ro:** `Backdrop.jsx` med tre z-lag: blurede nebula-
gradients (drift 66–90s, parallax pr. lag), canvas med 78 partikler i 3
dybdelag (sinus-twinkle, rAF-pause-mønster fra `Wings.jsx`), cards i
forgrunden. Glassmorphism på alle cards (blur 16px, inset-highlight, blød
skygge) + én accent-border-glow pr. card; Kalender (vigtigst) har statisk
svag gradient-border. `useCountUp`-hook (ease-out 800ms) på talværdier og
blødt opacity-lysskifte via `pulseKey` når et cards data opdateres.

**DEL 3 — tid + vejr:** `lib/daycycle.js` interpolerer blødt mellem fire
paletter (morgen/dag/aften/nat) og skriver `--tod-*`-vars hvert minut —
baggrund, nebula, planet og orbit-skærm trækker fra dem. `Planet.jsx`
øverst på hovedskærmen: layered gradients, terminator der vandrer med
døgnet, skylag ved skyet (hurtigere ved blæst), svage regn-streaks +
køligere tone ved regn, bylys om natten. Vejret vises bevidst både her og
i hero'en.

**DEL 5 — /ambient/orbit:** Sekundær 1920×1080-fuldskærm
(`orbit/OrbitScreen.jsx`): central orb (blød glød, breathing 8s), to tynde
ringe, korrektionsrate som ring-gauge, 7b/32b som måner skaleret efter
kørselsandel, stats i næsten usynlige glas-paneler med CountUp,
event-partikler der kredser ind og absorberes (1.5s opacity-ease + fadende
label), stort ur + næste aftale, cursor skjules efter 3 s.

## Nye endpoints (brain)

- `GET /api/ambient/stats` — aggregat fra `ambient_stats.py`, cachet 45 s
  i processen. Felter uden datagrundlag er `null` (aldrig opfundne tal).
- `GET /api/ambient/events?after_id=&limit=` — seneste rækker fra den nye
  `sys_events`-tabel (kun `kind`/`label`, aldrig privat indhold — ambient
  er en delt flade). Polles af orbit-skærmen hvert 10. sekund.

## Datagrundlag pr. stat

**Historisk ægte fra dag ét** (udledt af eksisterende tabeller):
- 7b-kørsler (pass 1) = alle rækker i `review_queue`
- 32b-reviews (pass 2) = rækker med status ≠ `pending`
- Gmail-triage i dag = `aula_messages` (begge streams) modtaget i dag

**Kun fremadrettet** (ny letvægts `sys_events`-log; `stats_since` i kv
markerer starten — vises som "indsamler data…" indtil der er data):
- Prompts (i dag + total) — logges i `telegram.handle_update`
- Korrektionsrate — `review.drain` logger pr. pass2-outcome
  (`corrected`/`done`/`expired`; korrigerede items har nu status
  `corrected` i `review_queue`). Historiske `done`-rækker kan have været
  korrektioner og indgår derfor bevidst IKKE i raten.
- Vikunja-writes i dag — logges i `vikunja.py`s skrive-funktioner
- Travleste time (highlight) — histogram over dagens `sys_events`

## Verifikation

- `npm run build` (3 sider) og `python -m compileall brain/app`: OK.
- Røgtest af stats-aggregeringen mod tom temp-DB (null-felter, tællere,
  events-cursor, pass1/pass2-split): OK.
- De to nye endpoints er tynde wrappers om den røgtestede aggregering;
  de er ikke integrationstestet mod en kørende FastAPI i dette miljø.

# Warm Paper — sekundært ambient-tema (design)

**Dato:** 2026-07-19
**Status:** godkendt i brainstorm; klar til implementeringsplan
**Reference-mockups:** `LifeHub family dashboard/design_handoff_lifehub/LifeHub Dashboard.dc.html` — skærm 1d (tablet dag), 1e (tablet nat), 1f (ultrawide), 1g (panel)

## Formål og afgrænsning

Warm Paper er et **sekundært** tema — det eksisterende space-tema forbliver default og røres ikke. Temaet vælges **udelukkende via URL** (ingen toggle-UI, ingen automatisk temaskift). Tre nye flader:

| Rute | Flade | Opløsning | Interaktiv? |
|---|---|---|---|
| `/paper/tablet` | Familie-dashboard (docket Pixel Tablet) | 2560×1600 | Nej (ren visning) |
| `/paper/wallpaper` | Ultrawide ambient-lag bag vinduer | 5120×1440 | Nej |
| `/paper/panel` | Handlingspanel (sekundær skærm) | 1920×1080 | Ja (triage-handlinger) |

Eksisterende ruter (`/`, `/ambient`, `/ambient/orbit`) er uændrede. Valgt rute-skema er `/paper/*`-gruppen (fremfor spec-udkastets `/tablet/paper`-suffikser), så alle Warm Paper-sider bor i én mappe og ingen enheds-URL'er ændres.

## Arkitektur (valgt: separat komponent-træ, delt datalag)

Warm Paper er ikke en omfarvning — layout, indholdshierarki og struktur (hairlines i stedet for cards, ingen ikoner) afviger fra space-temaet. Derfor: egne præsentationskomponenter, delt datalag.

```
dashboard/src/pages/paper/
  tablet.astro       → <PaperTablet client:load>
  wallpaper.astro    → <PaperWallpaper client:load>
  panel.astro        → <PaperPanel client:load>

dashboard/src/components/paper/
  PaperTablet.jsx
  PaperWallpaper.jsx
  PaperPanel.jsx
  usePaperData.js    (poll-hook om fetchDashboard; samme kadence som space; {doc, error, refresh})
  paperNight.js      (dag/nat ud fra doc.weather.sunrise/sunset; genbruger daycycle.js hvis
                      båndene passer, ellers en lille solnedgangs-check)

dashboard/src/styles/paper.css   (alle tokens + keyframes; importeres KUN af paper-sider)
dashboard/public/fonts/          (+ instrument-sans 400/500/600 woff2, self-hosted)
```

Genbruges uændret: `lib/api.js`, `lib/format.js`, `lib/mock.js` (dev-fallback), `layouts/Base.astro`. `global.css` og alle space-komponenter røres ikke; `@font-face` for Instrument Sans ligger i `paper.css`, så space-temaet aldrig henter de fonte.

## Designsprog (tokens i `paper.css`, på `.paper-root`)

- Papir: `#f4f0e8` (tablet/panel), `#f1ede4` (ultrawide)
- Blæk `#2a2520` · sekundær `#55493d` · dæmpet `#7a7267` · svag `#b6ada0`
- Én accent: terracotta `#b95c38`, mørk `#93482c`, tint `rgba(185,92,56,.12)` — accent betyder KUN "i dag/haster"
- Status (kun panel-DRIFT): grøn `#5c8a5a`, gul `#c9a23c`
- Hairlines `rgba(42,37,32,.10–.14)`; ingen cards, ingen skygger, ingen ikoner ud over statusprikker/opgavecirkler, ingen emoji
- Nat (`.paper-root[data-mode="night"]`): bg `#211d19`, tekst `#e8e0d3`/`#bdb2a0`, accent `#c98a67`, højrekolonne 75 % opacitet — samme variabelnavne, kun nye værdier
- Typografi: Instrument Sans 400/500/600 (tracking −0.03…−0.045em på store grader); IBM Plex Mono til labels/meta/data, UPPERCASE, letter-spacing .14–.18em; dansk, sentence case i indhold; `tnum` på ure
- Min. tekststørrelse: tablet ≈ 32px @2560; panel ≈ 13px mono / 16px brød @1920
- Keyframes `lh-drift-a/b`, `lh-sway`, `lh-breathe`; driftvarigheder som CSS-variabler (`--drift-dur-*`), produktionsdefault ≥300s pr. krydsning (mockuppens 60–90s er demo). `@media (prefers-reduced-motion: reduce)` slukker al drift/sway/breathe.

## Backend (alle ændringer additive, i `brain/`)

1. **Shopping-blok**: `/api/dashboard`-dokumentet udvides med
   `shopping: { items: [{id, title}], stale }` fra `vikunja.shopping_inventory()`s åbne bucket.
   Bruges kun af tablet-INDKØB. Ambient-dokumentet får den ikke.
2. **Triage-handlinger**: `POST /api/post/{item_id}/action` med body `{action}`:
   - `approve` → opret opgave, som Telegram-✅ (genbruger `aula.approve_item`)
   - `archive` → afvis/afslut (genbruger reject-flowet)
   - `defer` → forbliver pending, sætter `deferred_until` (skjules i panelet til næste dag)
   Plus `POST /api/post/archive-newsletters` til den kollapsede lavprioritetsrække.
   Admin-gates på samme måde som `/api/brief/regenerate`. Telegram-flowet forbliver
   semantisk kilde — endpoints kalder samme funktioner.
3. **Drift-status**: `GET /api/panel/status` → rækker pr. tjeneste
   (brain-latens, vikunja/gmail-triage/aula seneste sync, ollama-tilgængelighed) bygget af
   det, `ambient_stats`/store allerede måler. Kun reelle metrikker — ingen opdigtede tal.
4. Panelet henter det **ikke-ambiente** dokument (admin-flade; `post` er tilladt der).
   **Finans vises aldrig på nogen paper-flade.**

## Flader

### `/paper/tablet` (mockup 1d/1e)

- Grid 1.05fr/1fr, 140px gap, padding 110/120px. Hero-ur 400px vægt 600, live minutter;
  dato + aktuel temp under; én vejr-sætning fra weather-blokken.
- **I DAG**: maks 2 emner via lille selector — først dagens næste tidsatte event, dernæst
  mest presserende opgave/Aula-handling. Fyldt prik = haster (terracotta), outline = bemærkelsesværdig.
- Højrekolonne bag hairline: **OPGAVER** (4 tidligst-forfaldne Vikunja-opgaver; terracotta-ring +
  mono-frist når forfald i dag; seneste afsluttede vises gennemstreget) · **INDKØB** (outline-pills
  fra shopping-blokken; emoji strippes) · **SKOLE** (Aula-rækker; klassebadge udtrækkes fra
  `2.B`-agtigt præfiks når det findes, ellers neutralt badge).
- **Nat** (efter `weather.sunset`, før sunrise; tjekkes ved minut-tick): `data-mode="night"`,
  hero viser **I MORGEN** (morgendagens første event, ellers "ingen aftaler"-linje + forecast
  hvis tilgængelig), OPGAVER I MORGEN filtrerer på morgendagens frister, højrekolonne 75 %.
- Ren visning — tryk gør ingenting.

### `/paper/wallpaper` (mockup 1f)

- Absolut-positionerede vinger; center ≥2900px helt tomt (vinduer bor der).
- Venstre vinge (150px ind, 900px bred): UGEDAG · UGE NN (mono), 560px dato-tal, måned/år,
  nederst temp + vejrsætning + solop-/nedgang (mono).
- Højre vinge (820px): DE NÆSTE DAGE — 3 dage fra kalenderen med event-badges (accent-tint)
  og vejr pr. dag hvis forecast findes, ellers kun badge. Nederst én blid note = dagens mest
  bemærkelsesværdige event med 7s breathing-prik.
- Motion: 4 slørede radiale lyspletter, horisontal drift over hele bredden (`--drift-dur-*`,
  produktionsdefault ≥300s), vertikal sway ~26px på vinger (90s/110s, forskudt), breathe 7s.
  Alt slukket ved `prefers-reduced-motion`.
- Data: ambient-dokumentet (aldrig post/finans). Intet handlingsbart, intet der haster.

### `/paper/panel` (mockup 1g)

- Header: LifeHub / HANDLINGSPANEL (mono) / dato + live mono-ur; tung 2px-linje under.
- 3 kolonner (460px / 1fr / 430px, hairlines imellem):
  - **OPGAVER**: frist-sorterede Vikunja-opgaver; mono-frister ("i dag inden 14:00"-stil via
    `format.js`); terracotta ved frist i dag; bundlinje "+ N uden frist".
  - **INDBAKKE · TIL GENNEMSYN**: post-triage-emner — afsender, kategori-badge mappet fra
    `sender_kind`/intent (REGNING, SKOLE, INFO, LAV PRIORITET), én summary-linje, og
    **én primær outline-pill + én stille teksthandling**:
    handling-intent → "Opret opgave: …" / "Arkivér"; info-intent → "Læs & kvittér" (afslutter) /
    "Senere" (defer). Nyhedsbreve kollapses til én række med "Arkivér alle".
    Optimistisk UI: rækken fader ud ved handling; genindsættes med stille inline-notits ved fejl.
  - **SKOLE/AULA**: detaljerækker (badge, titel, mono-dato, summary) · nederst **DRIFT**-footer
    bag hairline: statusprik (grøn/gul, fx "seneste sync > 2 t = gul") + mono-metrik pr. tjeneste
    fra `/api/panel/status`, pollet hvert 60. sekund.

## Fejlhåndtering (alle flader)

Som space-temaet: behold sidste gode dokument ved fetch-fejl; vis én stille mono-linje i svag
blæk ("opdateret 14:32 · offline") — aldrig alarmtilstand. Dev falder automatisk tilbage til
`mock.js`. Panel-handlinger: optimistisk med genindsættelse + stille fejlnotits.

## Test og verifikation

- `astro build` skal bestå.
- Hver rute efterses i dev mod mockups i ægte opløsning (browser-screenshots @2560×1600,
  5120×1440, 1920×1080).
- Backend-endpoints afprøves med curl mod dev-brain (approve/archive/defer, archive-newsletters,
  panel-status). Handlingerne genbruger eksisterende funktioner, så Telegram-flowets semantik
  er uændret.
- `prefers-reduced-motion` verificeres via emulering.

# Handoff: LifeHub — family life dashboard (PWA)

## Overview
LifeHub is a self-hosted family dashboard in Danish with two layouts sharing one visual identity:

1. **Interaktiv visning** (`LifeHub Interaktiv.dc.html`) — phone-first, installable PWA, also desktop browser. Flowing card layout of widgets with tappable rows and checkable tasks.
2. **Ambient visning** (`LifeHub Ambient.dc.html`) — read-only wallpaper for a 5120×1440 super-ultrawide, with a standalone center-zone mode for a kitchen tablet (16:10, 1920×1200). Runs 24/7 behind desktop icons.

The feeling is a calm airport/train departure board (afgangstavle): glanceable, quiet, confident. Dark theme only. One accent color ("signal" amber) used sparingly for times, "now", and overdue states.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly. The task is to **recreate these designs in the target codebase's environment** (React, Vue, plain web components — whatever the PWA stack is) using its established patterns. If no environment exists yet, a lightweight PWA stack (e.g. Vite + vanilla/Preact, service worker, web app manifest) is appropriate — the design has no heavy dependencies.

The `.dc.html` files open directly in a browser. The markup lives between `<x-dc>` tags; the logic is a plain JS class at the bottom of each file. All demo data (family Ravn, events, tasks) is hardcoded in the logic classes — replace with real data sources.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and interactions are final. Recreate pixel-perfectly. `tokens.css` contains the complete token set as CSS variables — lift it directly.

## Design Tokens
See **`tokens.css`** (included, Danish-commented). Summary:

- Backgrounds: app `#0A1120`, ambient space `#060B16`, card `#0F1728`, hero card gradient `#101A2E → #0E1626`
- Text: primary `#E9EEF7`, body `#DCE4F2`, secondary `#93A0B8`, muted `#5B6A85`, faintest `#3E4B63`
- Signal (single accent): `#F0A22E`; glow `rgba(240,162,46,0.5)`; dim rings `rgba(240,162,46,0.22)`
- Borders: card `rgba(148,163,190,0.13)`, row dividers `rgba(148,163,190,0.08)`
- Fonts: **Space Grotesk** (UI) + **IBM Plex Mono** (ALL numbers/times, always `font-variant-numeric: tabular-nums`) — Google Fonts, weights 400/500/600 and 300/400/500
- Radius: cards 12px, checkboxes 6px
- Spacing scale: 4/8/12/16/20/24/32/48/64

## Language rules
All UI text in **Danish, sentence case** ("Middag i aften", not "Middag I Aften"). Danish number formats: `1,42 kr/kWh`, `14.382 kr.`, times `HH:MM` 24h. No finance content may ever appear in the ambient layout.

## Screens / Views

### 1. Interaktiv visning
Max-width 1240px, centered, padding clamp(16–36px). Page bg `#0A1120`.

**Top bar** — flex, space-between: "LifeHub" (19px/600, letter-spacing 0.04em) + 6px amber dot; right side: live clock (Plex Mono 14px, `#93A0B8`) + link to ambient view (13px `#5B6A85`, underline via border-bottom).

**Layout** — hero card full-width with 14px margin below, then a `display:flex; flex-wrap:wrap; gap:14px; align-items:flex-start` row where every card has `flex:1 1 330px; min-width:min(100%, 330px)`. Cards flow like text, lean left, stretch to fill each row. This is why the grid never looks broken when Økonomi is hidden — cards reflow naturally. On phones everything stacks to one column.

**Card anatomy** (all widgets): bg `#0F1728`, 1px border `rgba(148,163,190,0.13)`, radius 12px, padding 20px 22px. Header row: label 13px/500 `#93A0B8` letter-spacing 0.02em, optional right-aligned meta in Plex Mono 11.5px `#5B6A85`. Rows separated by 1px `rgba(148,163,190,0.08)` top borders, hover bg `rgba(148,163,190,0.05)`.

**Widgets:**
- **Dagens brief (hero)** — gradient bg, meta-line first (Plex Mono 13px: date in amber, then `·`-separated weather + elpris in `#93A0B8`), then 4–6 lines of AI-written morning text, 18px, line-height 1.68, `#DCE4F2`, max-width 70ch, `text-wrap:pretty`.
- **Kalender** — next 7 days grouped by day. Day label Plex Mono 11.5px `#5B6A85` ("I dag · onsdag 1. juli"). Event rows: grid `56px 1fr`, time Plex Mono 14px **amber**, title 14.5px `#E9EEF7`, location 12.5px `#5B6A85` beneath.
- **Opgaver** — header meta "N åbne". Rows: grid `22px 1fr auto`; 20×20 checkbox (radius 6, 1.5px border; overdue border `rgba(240,162,46,0.6)`); title 14.5px (done: `#5B6A85` + line-through); due label Plex Mono 12px right-aligned — overdue: amber text + 6px amber dot; else `#5B6A85`. Click row toggles done.
- **Fødselsdage** — next 30 days. Grid `100px 1fr auto` (date column nowrap): date Plex Mono 13px `#93A0B8` ("søn 5. jul."), name 14.5px, "fylder N" Plex Mono 12px `#5B6A85`.
- **Middag i aften** — dish 19px/500, cook 13.5px `#93A0B8`, divider, reminder note 13px `#5B6A85`.
- **Afgange** — header meta "Lyngby st. → København H". Rows: time Plex Mono 15px amber + relative ("om 7 min") Plex Mono 12.5px `#93A0B8`. Demo departures every 10 min at :x4.
- **Økonomi (private)** — visible only to permitted users. Header has a "privat" chip (Plex Mono 10.5px, 1px border, radius 4) and a "Skjul" text action. Account rows name/amount (amounts Plex Mono 14.5px tabular). "Seneste" section: 3 recent expenses, negative amounts. On-track indicator: 7px neutral dot + "På sporet · 8 % af juli-budgettet brugt". When hidden, a "Vis økonomi" action appears in the footer. **No layout shift when absent** (guaranteed by the flex-wrap flow).
- ~~Indkøbsliste~~ — **removed by client decision** (they use Nemlig.com).

**Footer** — divider, Plex Mono 11.5px `#3E4B63`: "LifeHub · selvhostet · familien Ravn".

### 2. Ambient visning
Fixed 5120×1440 stage, scaled to fit viewport (`transform:scale`). Bg: radial gradient `#0A1120 → #070D19 → #060B16`. Three zones:

**Center (~1800px) — functional core.** Also the entire tablet view (1920×1200 stage, center scaled 0.833, wings hidden). Readable from 3 m. Two columns, 56px gap:

- **Orbit clock (signature element)** — 780×780. A 24-hour dial: midnight at top, ring radius 310px, 1px `rgba(240,162,46,0.22)`; inner ring r=240 `rgba(148,163,190,0.10)`. Hour marks 00/06/12/18 at r=352, Plex Mono 15px `#3E4B63`. A 4×22px amber "now" tick sits on the ring at the current time, rotated tangentially, glow `0 0 12px rgba(240,162,46,0.6)`. **Today's events are planets on the dial**, positioned by time of day: upcoming = 13px amber dot with glow, drifting inward from r=310 toward r=240 as they approach (linear over the final 4 h); past = 10px `#5B6A85` at r=240, opacity 0.35. Each planet has a label at r+62: time (Plex Mono 17px, amber if upcoming) over title (18px `#93A0B8`). Sunrise/sunset are 9px hollow markers (1.5px amber border) on the ring with labels "solopgang"/"solnedgang". Dial center: clock Plex Mono 132px/300 `#E9EEF7` tabular, date 29px `#93A0B8`, "uge N" Plex Mono 18px `#5B6A85` (ISO week).
- **Functional column** — morning brief as hero text (36px, line-height 1.48, `#DCE4F2`, max 34ch); **Kalender**: 6 departure-style rows, grid `220px 1fr auto` — time Plex Mono 29px (today amber, other days `#93A0B8` with weekday prefix "tor " in `#5B6A85`), title 29px/500 ellipsized, location 20px `#5B6A85`; **Opgaver**: top 3, dot (9px; amber if overdue) + title 25px + due Plex Mono 19px (amber if overdue); **meta-line**: Plex Mono 22px `#93A0B8`, single line nowrap: `18° letskyet · elpris 1,42 kr/kWh · lav · Lyngby st. HH:MM · HH:MM` (2 next departures). Section labels: Plex Mono 16px, letter-spacing 0.1em, `#5B6A85`.

**Wings (~1660px each) — ambient solar systems.** No text, no data. Each wing: ~150 procedural stars (0.8–2.6px, `#AFC0DC`, opacity 0.08–0.40, seeded random so composition is stable); amber sun (radial gradient `#FFE0AC → #F0A22E → #C77E1F`, soft glow halo); 6 concentric 1px orbit rings (alternating faint amber/slate, opacity 0.05–0.10); 5 planets per wing as dots (7–15px, palette `#C08A4A #6E7F9C #4E5F7E #55627A`), one with a Saturn-style ring ellipse. Left system: sun 90px at (720,760); right: sun 64px at (940,680), different ring radii/phases so wings aren't mirrored. Wings tolerate partial coverage by desktop icons — nothing critical anywhere.

## Interactions & Behavior

**Interactive view:**
- Task row click → toggle done (checkbox fills, title struck through + muted, count updates)
- Økonomi "Skjul" ↔ footer "Vis økonomi"
- Clock updates every 15 s; departure times computed relative to now
- Hover on rows: bg `rgba(148,163,190,0.05)`; no transitions needed

**Ambient view — motion (all CSS keyframes, transform/opacity only, GPU-cheap, smooth-at-30 target):**
- Planet orbits: `rotate 0→360deg` linear infinite, periods **260–1400 s**, a couple reversed. Structure: a 0×0 anchor at the sun rotates; the planet child is `rotate(phase) translateX(radius)`.
- Star twinkle: ~16 % of stars, opacity 0.10↔0.55, 6–15 s ease-in-out, random negative delays
- Wing drift: each whole wing translates ±~15px over 110 s / 140 s ease-in-out alternate (different per wing)
- Sun breathing: glow halo opacity 0.7↔1.0 over 36 s / 44 s
- **Meteors**: two streaks crossing the full stage behind the center zone. Meteor A: 130×2px white gradient tail, travels (0,0)→(−2600,1240) in the first 9 % of a 52 s cycle, fades in at 1.5 %, out by 9 %; rotated 154.5° to match its path. Meteor B: 90×1.5px blue-tinted, opposite direction, 73 s cycle. Negative animation delays stagger them.
- **Reduced motion**: `@media (prefers-reduced-motion: reduce)` kills ALL animation (`animation:none !important`) — the frozen composition must look like a deliberate still. Also a manual kill-switch (data attribute) for the tablet.
- Tablet mode shows center zone only, completely static chrome-wise; meteors and wings absent.
- Clock re-renders every 1 s (only text changes; scene elements are memoized so CSS animation state survives re-renders — important detail when recreating in React: don't remount animated nodes on tick).

## State Management
- Interactive: `done` map (task id → bool), Økonomi hidden bool (per-user permission + session toggle), tick timer
- Ambient: mode (`ultrawide` | `tablet`), motion enabled bool, tick timer; star fields generated once from fixed seeds and cached
- Real implementation needs: calendar feed, tasks, birthdays, meal plan, train departures (Rejseplanen), weather, elpris (e.g. elprisenligenu/Energi Data Service), AI-written morning brief, and per-user auth for Økonomi

## Assets
None. No images or icon fonts — everything is CSS. Fonts from Google Fonts (Space Grotesk, IBM Plex Mono); self-host them for the PWA/wallpaper use case.

## Files
- `LifeHub Interaktiv.dc.html` — interactive view (markup + logic + demo data)
- `LifeHub Ambient.dc.html` — ambient view (markup + logic + scene animation)
- `tokens.css` — complete design-token set as CSS variables
- `support.js` — prototype runtime only; **ignore for implementation**

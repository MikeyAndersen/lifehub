# Morgenbrief: bedre dansk + klikbart opskrift-link

Dato: 2026-07-17

## Baggrund
To ønsker fra brugeren:
1. Briefens dansk er kluntet. (Der er ingen oversættelse — den skrives direkte
   på dansk af `qwen2.5:7b`. Årsagen er en tynd prompt uden struktur/eksempler,
   modsat de øvrige prompts i `llm.py`.)
2. Dagens ret på dashboardet skal med ét tryk kunne åbne opskriften på
   `madplan.nova-tech.dk`, når retten har en bundet opskrift.

Beslutninger: output forbliver dansk (vi strammer prompten, skifter ikke sprog).
Linket vises kun på dashboardet (ikke Telegram).

## Del 1 — Bedre dansk (lifehub, `brain/app/llm.py`)
Omskriv `compose_brief`-prompten:
- Fast struktur: åbningslinje → kun datapunkter der findes (kalender, opgaver,
  vejr) → afslutning. Maks 6 linjer.
- Ét dansk few-shot-eksempel (input-kontekst → ønsket brief).
- Eksplicit: naturligt dansk, ingen anglicismer, kun det der står i dataene.
Ingen ændring i kontekst, cache, Telegram eller frontend.

## Del 2 — Opskrift-link (to repos)

### nova-madplan (eksponér `recipe_id`)
- `api/app/models.py`: `Day` får `recipe_id: int | None = None`.
- `api/app/weekplan.py`: `build_weekplan`-SQL tager `di.recipe_id` med i join'et.
- Test: `/api/weekplan/current` returnerer `recipe_id` for en dag hvis rettens
  `recipe_id` er sat.

### lifehub dashboard (`dashboard/src/components/widgets/Ugeplan.jsx`)
- Har dagen `recipe_id`: rettens navn bliver et `<a>` mod
  `<PUBLIC_MADPLAN_BASE>/opskrifter/<recipe_id>` (ny fane, `rel=noopener`).
- Dage uden bundet opskrift = ren tekst som nu.
- Base-URL som `import.meta.env.PUBLIC_MADPLAN_BASE` med default
  `https://madplan.nova-tech.dk` (samme mønster som `PUBLIC_API_BASE`).
- Alle dage med bundet opskrift gøres klikbare (ikke kun i dag); i dag forbliver
  visuelt fremhævet.

Brain videresender allerede hele madplan-payloaden til dashboardet, så
lifehub/brain kræver ingen ændring.

## Rækkefølge / afhængighed
Linket dukker først op når nova-madplan er redeployet med `recipe_id` i
payloaden. Indtil da viser dashboardet retterne som ren tekst — ingen fejl.

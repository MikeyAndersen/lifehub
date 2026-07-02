/* ═══════════════════════════════════════════════════════════════
   MOCK DATA — kun til udvikling.
   Bruges KUN når `import.meta.env.DEV` og /api ikke svarer
   (se api.js). Formen matcher brain/app/dashboard.py's dokument.
   `madplan` og `transit` er fase 2-blokke; nøglerne her definerer
   frontend-kontrakten for dem (brain/app/feeds/stubs.py).
   ═══════════════════════════════════════════════════════════════ */

const p2 = (n) => String(n).padStart(2, '0');

/** ISO-dato/tid `off` dage fra i dag, kl. `hh:mm` (lokal tid). */
function at(off, hh, mm = 0) {
  const d = new Date();
  d.setDate(d.getDate() + off);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}T${p2(hh)}:${p2(mm)}:00`;
}
const day = (off) => at(off, 0).slice(0, 10);

export function mockDocument(ambient = false) {
  const nowH = new Date().getHours();
  const doc = {
    generated_at: new Date().toISOString(),
    brief: {
      text:
        'Godmorgen. Alma skal til svømning kl. 16, og Oscar har fodbold halv seks — huskeposen står i entréen. ' +
        'Elprisen er lav hele eftermiddagen, så det er en god dag at sætte en vask over. ' +
        'Vejret holder tørt til hen på aftenen; en let jakke er nok.',
      date: day(0),
    },
    events: [
      { title: 'Svømning — Alma', start: at(0, 16), all_day: false, calendar: 'familien', location: 'Lyngby svømmehal' },
      { title: 'Fodboldtræning — Oscar', start: at(0, 17, 30), all_day: false, calendar: 'familien', location: 'B.93, bane 4' },
      { title: 'Tandlæge — Jonas', start: at(1, 9), all_day: false, calendar: 'familien', location: 'Tandklinikken, Torvet 3' },
      { title: 'Legeaftale — Oscar hos Villads', start: at(1, 15), all_day: false, calendar: 'familien', location: 'Sorgenfri' },
      { title: 'Cykeltur til Dyrehaven', start: at(2, 10), all_day: false, calendar: 'familien', location: 'Alle' },
      { title: 'Fødselsdag hos farmor', start: at(3, 12), all_day: false, calendar: 'familien', location: 'Holte' },
      { title: 'Forældremøde — Alma', start: at(5, 19), all_day: false, calendar: 'familien', location: 'Trongårdsskolen' },
    ],
    birthdays: [
      { title: 'Farmor Kirsten (72)', date: day(3) },
      { title: 'Villads — Oscars ven (7)', date: day(12) },
      { title: 'Mette (41)', date: day(26) },
    ],
    tasks: [
      { id: 1, title: 'Bestil tid til bilsyn', due: at(-1, 17), project_id: 1 },
      { id: 2, title: 'Køb gave til farmor', due: at(0, 17), project_id: 1 },
      { id: 3, title: 'Vand tomaterne', due: at(0, 17), project_id: 1 },
      { id: 4, title: 'Betal Almas svømmekontingent', due: at(1, 17), project_id: 1 },
      { id: 5, title: 'Aflever biblioteksbøger', due: at(2, 17), project_id: 1 },
    ],
    weather: { now_c: 18.2, code: 2, wind_ms: 4.1, today_max: 21.0, today_min: 12.4, rain_pct: 20 },
    elpris: {
      now_dkk_kwh: 1.42,
      hours: Array.from({ length: 24 }, (_, h) => ({
        hour: `${day(0)}T${p2(h)}:00:00`,
        dkk_kwh: Math.round((0.9 + 1.4 * Math.abs(Math.sin((h - 4) / 5))) * 100) / 100,
      })),
    },
    // Fase 2-blokke — endnu ikke i det rigtige API-dokument:
    madplan: {
      tonight: { dish: 'Pasta med kødsauce', cook: 'Jonas laver mad', note: 'Husk: tag kødet ud af fryseren i eftermiddag' },
      status: 'ok',
    },
    transit: {
      station: 'Lyngby st.',
      direction: 'København H',
      departures: [at(0, nowH, 44), at(0, nowH + 1, 4), at(0, nowH + 1, 24)],
      status: 'ok',
    },
  };
  if (!ambient) {
    // Finans må ALDRIG med i ambient — heller ikke i mock.
    doc.finance = {
      accounts: [
        { name: 'Budgetkonto', balance_dkk: 14382 },
        { name: 'Opsparing', balance_dkk: 86150 },
      ],
      recent_expenses: [
        { title: 'Netto', amount_dkk: 247, noted_at: at(0, 9) },
        { title: 'DSB pendlerkort', amount_dkk: 112, noted_at: at(-1, 8) },
        { title: 'Apoteket', amount_dkk: 89, noted_at: at(-1, 15) },
      ],
      status: 'ok',
    };
  }
  return doc;
}

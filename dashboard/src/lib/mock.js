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

/** Mandagens ISO-dato i indeværende uge. */
function weekMonday() {
  const d = new Date();
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
}

/** Syntetisk §2.2-ugeplan: mandag→søndag, i dag markeret, fortid = cooked. */
function mockWeek() {
  const names = ['Kylling i karry', 'Tomatrisotto', 'Tacos', 'Fiskefrikadeller', 'Pizza', 'Rester', null];
  const wd = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag', 'lørdag', 'søndag'];
  const mon = new Date(`${weekMonday()}T00:00:00`);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return names.map((name, i) => {
    const d = new Date(mon); d.setDate(mon.getDate() + i);
    const date = `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
    const status = !name ? 'empty' : d < today ? 'cooked' : 'planned';
    return { date, weekday: wd[i], dish_id: name ? i + 1 : null, dish_name: name, status, note: null };
  });
}

/** Lokal ISO-tid `min` minutter fra nu (afgange). */
function inMin(min) {
  const d = new Date(Date.now() + min * 60000);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}T${p2(d.getHours())}:${p2(d.getMinutes())}:00`;
}

export function mockDocument(ambient = false) {
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
    tasks_done: [
      { id: 6, title: 'Ring til mor', done_at: at(0, 9, 15), project_id: 1 },
      { id: 7, title: 'Tøm opvaskemaskinen', done_at: at(-1, 19, 40), project_id: 1 },
    ],
    aula: {
      new_today: 2,
      info: [
        { title: 'Ugens bogstav er S', summary: 'Klassen arbejder med S i denne uge.', created_at: at(0, 8, 5), status: 'pending' },
        { title: 'Fotografen kommer i uge 29', summary: 'Skolefoto for hele indskolingen.', created_at: at(-1, 12, 0), status: 'briefed' },
      ],
      recent: [
        { title: 'Forældremøde', intent: 'event', status: 'auto_created', date: day(6), time: '17:00', created_at: at(0, 8, 5) },
        { title: 'Medbring skiftetøj til turdag', intent: 'handling', status: 'pending', date: day(2), time: null, created_at: at(0, 8, 5) },
      ],
    },
    weather: { now_c: 18.2, code: 2, wind_ms: 4.1, today_max: 21.0, today_min: 12.4, rain_pct: 20 },
    elpris: {
      now_dkk_kwh: 1.42,
      hours: Array.from({ length: 24 }, (_, h) => ({
        hour: `${day(0)}T${p2(h)}:00:00`,
        dkk_kwh: Math.round((0.9 + 1.4 * Math.abs(Math.sin((h - 4) / 5))) * 100) / 100,
      })),
    },
    // Fase 2-madplan: §2.2 WeekPlan (brain cacher madplans /api/weekplan/current).
    madplan: {
      week_start: weekMonday(),
      days: mockWeek(),
      updated_at: new Date().toISOString(),
      stale: false,
    },
    transit: {
      station: 'Lyngby st.',
      direction: 'København H',
      departures: [inMin(7), inMin(27), inMin(47)],
      status: 'ok',
    },
  };
  if (!ambient) {
    // Post-triage er admin-only som finans — aldrig i ambient, heller ikke i mock.
    doc.post = {
      new_today: 3,
      info: [
        { title: 'Årsopgørelse klar i TastSelv', summary: 'Skat: din årsopgørelse for 2025 er klar.', created_at: at(0, 7, 40), status: 'pending', importance: 'high', sender_kind: 'kommune' },
      ],
      recent: [
        { title: 'Forny indboforsikring', intent: 'handling', status: 'pending', date: null, time: null, created_at: at(0, 8, 10), deadline: day(5) + 'T23:59', importance: 'high', sender_kind: 'forsikring' },
        { title: 'Bekræft tandlægetid', intent: 'handling', status: 'approved', date: null, time: null, created_at: at(-1, 9, 0), deadline: day(2) + 'T12:00', importance: 'normal', sender_kind: 'sundhed' },
      ],
    };
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

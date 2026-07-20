/* Ren logik for Warm Paper-fladerne — ingen React, testes med node --test.
   Datoformer matcher brain-dokumentet (lokal ISO uden zone). */
import { fmtTime } from '../../lib/format.js';

/** Spec: ingen emoji på paper-flader — data kan indeholde dem (fx indkøb).
    \p{Extended_Pictographic} dækker ikke flag (Regional_Indicator-par) eller
    hudtone-modifikatorer, så de tilføjes eksplicit. Kollapser mellemrum
    efterladt af strippede tegn/ZWJ-sekvenser. */
export const stripEmoji = (s) =>
  (s || '')
    .replace(/[\p{Extended_Pictographic}\p{Regional_Indicator}\u{1F3FB}-\u{1F3FF}️‍]/gu, '')
    .replace(/\s+/g, ' ')
    .trim();

/** "2.B"/"5.A"/"SFO" i en titel → badge-tekst, ellers null.
    JS' \b er ASCII-only: Æ/Ø/Å tælles ikke som \w, så \b efter dem matcher
    ikke foran et mellemrum. Brug derfor eksplicitte grænser (ikke
    bogstav/ciffer på begge sider) i stedet for \b. */
export function classBadge(title) {
  const m = (title || '').match(/(?<![\p{L}\p{N}])(\d\.[A-ZÆØÅ]|SFO)(?![\p{L}\p{N}])/u);
  return m ? m[1] : null;
}

const KIND_LABELS = {
  kommune: 'KOMMUNE', bank: 'BANK', forsikring: 'FORSIKRING',
  sundhed: 'SUNDHED', skole: 'AULA', forening: 'FORENING',
  butik: 'BUTIK', nyhedsbrev: 'LAV PRIORITET', andet: 'INFO',
};

/** Kategori-badge for et post-emne. Accent kun ved importance=high. */
export function postBadge(item) {
  return {
    label: KIND_LABELS[item.sender_kind] || 'INFO',
    tone: item.importance === 'high' ? 'accent' : 'neutral',
  };
}

/** Pending post-emner delt i handlingsliste og nyhedsbreve (til én række). */
export function partitionInbox(post) {
  const pending = (list) => (list || []).filter((i) => i.status === 'pending');
  const all = [...pending(post?.recent), ...pending(post?.info)];
  return {
    actionable: all.filter((i) => i.sender_kind !== 'nyhedsbrev'),
    newsletters: all.filter((i) => i.sender_kind === 'nyhedsbrev'),
  };
}

/** Primær pille: handling → godkend (opret opgave), info → kvittér. */
export function primaryAction(item) {
  if (item.intent === 'handling') {
    return { label: `Opret opgave: ${stripEmoji(item.title)}`, action: 'approve' };
  }
  return { label: 'Læs & kvittér', action: 'archive' };
}

/** Stille handling: handling → arkivér, info → senere (defer). */
export function quietAction(item) {
  if (item.intent === 'handling') return { label: 'Arkivér', action: 'archive' };
  return { label: 'Senere', action: 'defer' };
}

const WDS = ['søn', 'man', 'tir', 'ons', 'tor', 'fre', 'lør'];
const sameDay = (a, b) => a.toDateString() === b.toDateString();

/** Forfalden ift. det injicerede `now` (til deterministiske tests), ikke det
    rigtige ur — spejler format.js' isOverdue, men parametriseret på `now`. */
const isOverdueAt = (iso, now) => {
  if (!iso) return false;
  const d = new Date(iso);
  const startOfDay = new Date(now);
  startOfDay.setHours(0, 0, 0, 0);
  return d < startOfDay;
};

/** Panelets frist-linje: "i dag inden 14:00" / "i morgen" / "ons 23.7." /
    "forfalden". null uden frist. */
export function dueLine(iso, now = new Date()) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isOverdueAt(iso, now) && !sameDay(d, now)) return 'forfalden';
  if (sameDay(d, now)) return `i dag inden ${fmtTime(iso)}`;
  if (sameDay(d, new Date(now.getTime() + 864e5))) return 'i morgen';
  return `${WDS[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
}

/** Tablet-heroens I DAG: maks 2 — først dagens næste tidsatte event (urgent),
    så mest presserende opgave, så pending Aula-handling. */
export function pickHighlights(doc, now = new Date()) {
  const out = [];
  const ev = (doc.events || []).find((e) => !e.all_day && e.start
    && sameDay(new Date(e.start), now) && new Date(e.start) > now);
  if (ev) out.push({ text: `${stripEmoji(ev.title)} kl. ${fmtTime(ev.start)}`, urgent: true });
  const task = (doc.tasks || []).find((t) => t.due
    && (isOverdueAt(t.due, now) || sameDay(new Date(t.due), now)));
  if (task && out.length < 2) {
    out.push({ text: stripEmoji(task.title), urgent: isOverdueAt(task.due, now) });
  }
  const aula = (doc.aula?.recent || []).find((i) => i.status === 'pending');
  if (aula && out.length < 2) out.push({ text: stripEmoji(aula.title), urgent: false });
  return out.slice(0, 2);
}

/** Nat-heroens I MORGEN-linje + morgendagens opgaver. */
export function tomorrowOverview(doc, now = new Date()) {
  const tomorrow = new Date(now.getTime() + 864e5);
  const ev = (doc.events || []).find((e) => e.start
    && sameDay(new Date(e.start), tomorrow));
  const wd = tomorrow.toLocaleDateString('da-DK', { weekday: 'long' });
  const cap = wd.charAt(0).toUpperCase() + wd.slice(1);
  const line = ev
    ? `${cap}: ${stripEmoji(ev.title)}${ev.all_day ? '' : ` kl. ${fmtTime(ev.start)}`}`
    : `${cap}: ingen aftaler`;
  const tasks = (doc.tasks || []).filter((t) => t.due
    && sameDay(new Date(t.due), tomorrow));
  return { line, tasks };
}

/** Wallpaperens DE NÆSTE DAGE: n dage frem med korte event-badges. */
export function nextDays(events, now = new Date(), n = 3) {
  return Array.from({ length: n }, (_, i) => {
    const day = new Date(now.getTime() + (i + 1) * 864e5);
    const badges = (events || [])
      .filter((e) => e.start && sameDay(new Date(e.start), day))
      .slice(0, 2)
      .map((e) => stripEmoji(e.title).split('—')[0].trim());
    return {
      weekday: day.toLocaleDateString('da-DK', { weekday: 'long' }),
      badges,
    };
  });
}

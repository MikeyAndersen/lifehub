/* Danske formaterings-hjælpere — delt af interaktiv og ambient visning. */

export const p2 = (n) => String(n).padStart(2, '0');

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** "16:00" fra ISO — eller "hele dagen" for heldagsdatoer. */
export const fmtTime = (iso) =>
  iso?.includes('T') ? iso.slice(11, 16) : 'hele dagen';

/** "HH:MM" for et Date-objekt. */
export const fmtClock = (d) => p2(d.getHours()) + ':' + p2(d.getMinutes());

const sameDay = (a, b) => a.toDateString() === b.toDateString();
const dayOffset = (iso) => {
  const d = new Date(iso);
  if (sameDay(d, new Date())) return 0;
  if (sameDay(d, new Date(Date.now() + 864e5))) return 1;
  if (sameDay(d, new Date(Date.now() - 864e5))) return -1;
  return null;
};

/** "I dag" / "I morgen" / "ons 8. jul." */
export const fmtDay = (iso) => {
  const off = dayOffset(iso);
  if (off === 0) return 'I dag';
  if (off === 1) return 'I morgen';
  return new Date(iso).toLocaleDateString('da-DK', { weekday: 'short', day: 'numeric', month: 'short' });
};

/** Kalender-gruppelabel: "I dag · onsdag 2. juli" / "Onsdag 8. juli". */
export const fmtDayGroupLabel = (iso) => {
  const base = new Date(iso).toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });
  const off = dayOffset(iso);
  if (off === 0) return 'I dag · ' + base;
  if (off === 1) return 'I morgen · ' + base;
  return cap(base);
};

/** Opgave-deadline: "i går" / "i dag" / "i morgen" / "ons 8." */
export const fmtDue = (iso) => {
  const off = dayOffset(iso);
  if (off === -1) return 'i går';
  if (off === 0) return 'i dag';
  if (off === 1) return 'i morgen';
  return new Date(iso).toLocaleDateString('da-DK', { weekday: 'short', day: 'numeric' }) + '.';
};

/** Fødselsdags-dato: "søn 5. jul." */
export const fmtBdDate = (iso) =>
  new Date(iso).toLocaleDateString('da-DK', { weekday: 'short', day: 'numeric', month: 'short' });

/** "Onsdag 2. juli" (interaktiv hero) / med årstal (ambient). */
export const fmtDateLine = (d, withYear = false) =>
  cap(d.toLocaleDateString('da-DK', {
    weekday: 'long', day: 'numeric', month: 'long', ...(withYear && { year: 'numeric' }),
  }));

/** Forfalden: deadline før i dag (kun dato-delen tæller). */
export const isOverdue = (iso) => {
  if (!iso) return false;
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
};

/** ISO-ugenummer. */
export function isoWeek(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  t.setUTCDate(t.getUTCDate() - ((t.getUTCDay() + 6) % 7) + 3);
  const firstThu = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
  return 1 + Math.round(((t - firstThu) / 864e5 - 3 + ((firstThu.getUTCDay() + 6) % 7)) / 7);
}

/** "1,42" — dansk decimalkomma. */
export const fmtDkk = (n, decimals = 2) =>
  n.toLocaleString('da-DK', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

/** "14.382 kr." — beløb med tusindtalspunktum. */
export const fmtKr = (n) => n.toLocaleString('da-DK', { maximumFractionDigits: 0 }) + ' kr.';

/** WMO-vejrkode → kort dansk beskrivelse. */
export function weatherLabel(code) {
  if (code === 0) return 'skyfrit';
  if (code <= 2) return 'letskyet';
  if (code === 3) return 'overskyet';
  if (code <= 48) return 'tåge';
  if (code <= 57) return 'støvregn';
  if (code <= 67) return 'regn';
  if (code <= 77) return 'sne';
  if (code <= 82) return 'byger';
  if (code <= 86) return 'snebyger';
  return 'torden';
}

/** Elpris-niveau nu ift. dagens spænd: "lav" / "normal" / "høj". */
export function elprisLevel(elpris) {
  if (elpris?.now_dkk_kwh == null || !elpris.hours?.length) return null;
  const prices = elpris.hours.map((h) => h.dkk_kwh);
  const min = Math.min(...prices), max = Math.max(...prices);
  if (max - min < 0.01) return 'normal';
  const t = (elpris.now_dkk_kwh - min) / (max - min);
  return t < 1 / 3 ? 'lav' : t > 2 / 3 ? 'høj' : 'normal';
}

/** "om 7 min" / "nu" for en ISO-afgangstid. */
export const fmtRel = (iso, now = new Date()) => {
  const diff = Math.round((new Date(iso) - now) / 60000);
  return diff <= 0 ? 'nu' : `om ${diff} min`;
};

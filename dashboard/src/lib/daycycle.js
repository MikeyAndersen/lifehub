/* Time-of-day theming (DEL 3): fire nøglepaletter (morgen/dag/aften/nat)
   interpoleres blødt efter klokken og skrives som CSS-vars på :root.
   Alle farver er RGB-tripler ("r g b") så opacity styres i CSS via
   rgb(var(--x) / a). Både hovedskærmen og /ambient/orbit trækker herfra. */

const ANCHORS = [
  //  h    bg (flade)      neb-a (cyan-agtig) neb-b (violet)   neb-c (varm)     tint (planet/orb-lys)
  { h: 0,    bg: [6, 9, 17],   a: [96, 126, 168],  b: [104, 96, 152],  c: [82, 104, 138],  tint: [148, 168, 205] }, // nat
  { h: 7,    bg: [14, 17, 28], a: [172, 158, 140], b: [188, 142, 158], c: [199, 176, 138], tint: [212, 186, 156] }, // morgen
  { h: 12.5, bg: [10, 17, 32], a: [132, 178, 196], b: [150, 138, 188], c: [199, 176, 138], tint: [176, 198, 220] }, // dag
  { h: 19.5, bg: [13, 13, 25], a: [150, 138, 188], b: [188, 142, 158], c: [186, 160, 132], tint: [196, 168, 186] }, // aften
  { h: 24,   bg: [6, 9, 17],   a: [96, 126, 168],  b: [104, 96, 152],  c: [82, 104, 138],  tint: [148, 168, 205] }, // nat igen
];

const smooth = (t) => t * t * (3 - 2 * t);
const lerp3 = (u, v, t) => u.map((x, i) => Math.round(x + (v[i] - x) * t));

/** Interpoleret palet for en decimaltime 0–24. */
export function paletteAt(hour) {
  const h = ((hour % 24) + 24) % 24;
  let i = 0;
  while (ANCHORS[i + 1].h < h) i++;
  const A = ANCHORS[i], B = ANCHORS[i + 1];
  const t = smooth((h - A.h) / (B.h - A.h));
  return {
    bg: lerp3(A.bg, B.bg, t),
    a: lerp3(A.a, B.a, t),
    b: lerp3(A.b, B.b, t),
    c: lerp3(A.c, B.c, t),
    tint: lerp3(A.tint, B.tint, t),
  };
}

/** 0 (nat) ↔ 1 (midt på dagen) — driver planetens/orbens lysside. */
export function daylight(hour) {
  // Cosinus om kl. 13 (dansk sommer-fornemmelse), klemt blødt til 0..1.
  const x = Math.cos(((hour - 13) / 24) * 2 * Math.PI);
  return smooth(Math.max(0, Math.min(1, 0.5 + 0.62 * x)));
}

const hourOf = (iso) => {
  const [h, m] = iso.slice(11, 16).split(':');
  return +h + +m / 60;
};

/* Solens tilstand ud fra RIGTIG solopgang/-nedgang (weather.sunrise/sunset).
   `up` = over horisonten, `altitude` 0 (horisont) → 1 (middag), `frac` 0→1
   hen over dagslyset. Uden sol-tider falder vi tilbage på cosinus-modellen.
   Bruges af orbit-planeten til at lade solen stå op og gå ned naturligt. */
export function sunState(now, sunrise, sunset) {
  const t = now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600;
  if (!sunrise || !sunset) {
    const alt = daylight(t);
    return { up: alt > 0.03, altitude: alt, frac: t / 24, night: alt <= 0.03 };
  }
  const sr = hourOf(sunrise), ss = hourOf(sunset);
  if (t < sr || t > ss) {
    // Nat: frac 0→1 fra solnedgang til næste solopgang (til stjerne/bylys-brug).
    const nightLen = 24 - (ss - sr);
    const into = (t < sr ? t + 24 - ss : t - ss);
    return { up: false, altitude: 0, frac: into / nightLen, night: true };
  }
  const frac = (t - sr) / (ss - sr);
  return { up: true, altitude: smooth(Math.sin(frac * Math.PI)), frac, night: false };
}

function apply() {
  const now = new Date();
  const p = paletteAt(now.getHours() + now.getMinutes() / 60);
  const s = document.documentElement.style;
  s.setProperty('--tod-bg', p.bg.join(' '));
  s.setProperty('--tod-neb-a', p.a.join(' '));
  s.setProperty('--tod-neb-b', p.b.join(' '));
  s.setProperty('--tod-neb-c', p.c.join(' '));
  s.setProperty('--tod-tint', p.tint.join(' '));
}

/** Start paletten (nu + hvert minut). Returnerer stop-funktion. */
export function startDaycycle() {
  apply();
  const id = setInterval(apply, 60_000);
  return () => clearInterval(id);
}

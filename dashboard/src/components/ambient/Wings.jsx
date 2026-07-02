import { useEffect, useRef } from 'react';

/* Ambient-vingerne — ét 2D-canvas over hele 5120×1440-scenen med ét
   requestAnimationFrame-loop. Ingen tekst, ingen data: to rolige
   solsystemer, spredte stjerner bag midterzonen og to sjældne meteorer.

   Renderes kun i ultrawide-tilstand (sideforhold > 21:9) — se Ambient.jsx.
   - prefers-reduced-motion: scenen fryses som ét bevidst stillbillede.
   - Loopet pauser når fanen er skjult (document.hidden) og når Wallpaper
     Engine melder pause via window.wallpaperPropertyListener.setPaused.  */

const W = 5120, H = 1440, WING = 1660;

const AMBER = (a) => `rgba(240,162,46,${a})`;
const SLATE = (a) => `rgba(148,163,190,${a})`;

/* Deterministisk RNG (mulberry32) — stjernehimlen er stabil mellem besøg. */
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeStars(seed, w, h, count, big) {
  const rnd = mulberry32(seed);
  const stars = [];
  for (let i = 0; i < count; i++) {
    const size = rnd() * (big ? 1.8 : 1.4) + 0.8;
    const twinkle = rnd() < 0.16;
    stars.push({
      x: rnd() * w, y: rnd() * h, r: size / 2,
      alpha: twinkle ? 0.4 : 0.08 + rnd() * 0.32,
      twinkle, dur: 6 + rnd() * 9, phase: rnd() * 12,
    });
  }
  return stars;
}

/* Geometrien er en 1:1-oversættelse af designfilens CSS-scene. */
const WINGS = [
  { // venstre vinge (scene-x 0–1660)
    ox: 0, starSeed: 1337,
    drift: { from: [-16, -10], to: [10, 12], period: 110 },
    sun: { x: 720, y: 760, r: 45, haloR: 210, breath: 36 },
    rings: [
      { r: 170, c: AMBER(0.10) }, { r: 270, c: SLATE(0.10) }, { r: 390, c: SLATE(0.08) },
      { r: 530, c: SLATE(0.07) }, { r: 690, c: AMBER(0.06) }, { r: 860, c: SLATE(0.05) },
    ],
    planets: [
      { r: 170, phase: 40, size: 12, color: '#C08A4A', period: 260 },
      { r: 270, phase: 160, size: 8, color: '#6E7F9C', period: 420 },
      { r: 390, phase: 255, size: 15, color: '#4E5F7E', period: 640, reverse: true },
      { r: 530, phase: 105, size: 10, color: '#6E7F9C', period: 960 },
      { r: 690, phase: 320, size: 7, color: '#55627A', period: 1300 },
    ],
  },
  { // højre vinge (scene-x 3460–5120) — andre radier/faser, ikke spejlet
    ox: W - WING, starSeed: 9021,
    drift: { from: [12, 10], to: [-10, -12], period: 140 },
    sun: { x: 940, y: 680, r: 32, haloR: 190, breath: 44 },
    rings: [
      { r: 150, c: AMBER(0.10) }, { r: 240, c: SLATE(0.10) }, { r: 350, c: SLATE(0.08) },
      { r: 480, c: SLATE(0.07) }, { r: 640, c: AMBER(0.06) }, { r: 820, c: SLATE(0.05) },
    ],
    planets: [
      { r: 150, phase: 210, size: 10, color: '#C08A4A', period: 300 },
      { r: 240, phase: 70, size: 14, color: '#A9B7CE', period: 480, ringed: true },
      { r: 350, phase: 330, size: 8, color: '#6E7F9C', period: 720, reverse: true },
      { r: 480, phase: 130, size: 12, color: '#4E5F7E', period: 1040 },
      { r: 640, phase: 20, size: 7, color: '#55627A', period: 1400 },
    ],
  },
];

const METEORS = [
  { x0: 3400, y0: -80, dx: -2600, dy: 1240, cycle: 52, delay: 10, frac: 0.09, fadeIn: 0.015, maxA: 0.9, len: 130, w: 2, tail: 'rgba(233,238,247,0)', mid: 'rgba(233,238,247,0.85)', head: '#FFFFFF' },
  { x0: 600, y0: 1350, dx: 2100, dy: -950, cycle: 73, delay: 40, frac: 0.07, fadeIn: 0.012, maxA: 0.6, len: 90, w: 1.5, tail: 'rgba(175,192,220,0)', mid: 'rgba(175,192,220,0.7)', head: '#E9EEF7' },
];

const CENTER_STARS = makeStars(4242, 1800, H, 45, false);
const WING_STARS = WINGS.map((wing) => makeStars(wing.starSeed, WING + 60, H + 60, 150, true));

/* Ping-pong 0→1→0 med blød ind-/udgang (svarer til ease-in-out alternate). */
function pingpong(t, period) {
  const p = (t / period) % 2;
  const tri = p < 1 ? p : 2 - p;
  return tri * tri * (3 - 2 * tri);
}

const breathe = (t, period) => 0.7 + 0.3 * (0.5 - 0.5 * Math.cos((2 * Math.PI * t) / period));

function drawStars(ctx, stars, t) {
  ctx.fillStyle = '#AFC0DC';
  for (const s of stars) {
    ctx.globalAlpha = s.twinkle
      ? 0.10 + 0.45 * (0.5 - 0.5 * Math.cos((2 * Math.PI * (t + s.phase)) / s.dur))
      : s.alpha;
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, 2 * Math.PI);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function drawWing(ctx, wing, stars, t) {
  const { sun } = wing;
  const k = pingpong(t, wing.drift.period);
  const dx = wing.drift.from[0] + (wing.drift.to[0] - wing.drift.from[0]) * k;
  const dy = wing.drift.from[1] + (wing.drift.to[1] - wing.drift.from[1]) * k;

  ctx.save();
  ctx.beginPath();
  ctx.rect(wing.ox, 0, WING, H);
  ctx.clip();
  ctx.translate(wing.ox + dx - 30, dy - 30); // inset:-30 som i designet

  drawStars(ctx, stars, t);

  // Åndende glød-halo + sol
  ctx.globalAlpha = breathe(t, sun.breath);
  const halo = ctx.createRadialGradient(sun.x, sun.y, 0, sun.x, sun.y, sun.haloR);
  halo.addColorStop(0, AMBER(0.15));
  halo.addColorStop(0.7, AMBER(0));
  halo.addColorStop(1, AMBER(0));
  ctx.fillStyle = halo;
  ctx.fillRect(sun.x - sun.haloR, sun.y - sun.haloR, sun.haloR * 2, sun.haloR * 2);
  ctx.globalAlpha = 1;

  const body = ctx.createRadialGradient(
    sun.x - sun.r * 0.28, sun.y - sun.r * 0.32, 0, sun.x, sun.y, sun.r,
  );
  body.addColorStop(0, '#FFE0AC');
  body.addColorStop(0.58, '#F0A22E');
  body.addColorStop(1, '#C77E1F');
  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.arc(sun.x, sun.y, sun.r, 0, 2 * Math.PI);
  ctx.fill();

  ctx.lineWidth = 1;
  for (const ring of wing.rings) {
    ctx.strokeStyle = ring.c;
    ctx.beginPath();
    ctx.arc(sun.x, sun.y, ring.r, 0, 2 * Math.PI);
    ctx.stroke();
  }

  for (const pl of wing.planets) {
    const spin = ((t / pl.period) * 360) % 360;
    const deg = pl.phase + (pl.reverse ? -spin : spin);
    const th = (deg * Math.PI) / 180;
    const px = sun.x + pl.r * Math.cos(th);
    const py = sun.y + pl.r * Math.sin(th);
    ctx.fillStyle = pl.color;
    ctx.beginPath();
    ctx.arc(px, py, pl.size / 2, 0, 2 * Math.PI);
    ctx.fill();
    if (pl.ringed) { // Saturn-agtig ring-ellipse
      ctx.save();
      ctx.translate(px, py);
      ctx.rotate((-24 * Math.PI) / 180);
      ctx.strokeStyle = 'rgba(169,183,206,0.45)';
      ctx.beginPath();
      ctx.ellipse(0, 0, 16, 5.5, 0, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.restore();
    }
  }

  ctx.restore();
}

function drawMeteor(ctx, m, t) {
  const c = ((t + m.delay) / m.cycle) % 1;
  if (c >= m.frac) return;
  const alpha = c < m.fadeIn
    ? m.maxA * (c / m.fadeIn)
    : m.maxA * (1 - (c - m.fadeIn) / (m.frac - m.fadeIn));
  const k = c / m.frac;
  const hx = m.x0 + m.dx * k, hy = m.y0 + m.dy * k;
  const d = Math.hypot(m.dx, m.dy);
  const ux = m.dx / d, uy = m.dy / d;
  const tx = hx - ux * m.len, ty = hy - uy * m.len; // halen slæber bag hovedet
  const grad = ctx.createLinearGradient(tx, ty, hx, hy);
  grad.addColorStop(0, m.tail);
  grad.addColorStop(0.82, m.mid);
  grad.addColorStop(1, m.head);
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = grad;
  ctx.lineWidth = m.w;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(tx, ty);
  ctx.lineTo(hx, hy);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function drawScene(ctx, t) {
  ctx.clearRect(0, 0, W, H);
  WINGS.forEach((wing, i) => drawWing(ctx, wing, WING_STARS[i], t));
  ctx.save();
  ctx.translate((W - 1800) / 2, 0); // spredte stjerner bag midterzonen
  drawStars(ctx, CENTER_STARS, t);
  ctx.restore();
  for (const m of METEORS) drawMeteor(ctx, m, t);
}

export default function Wings() {
  const ref = useRef(null);

  useEffect(() => {
    const ctx = ref.current.getContext('2d');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let raf = 0, running = false, wePaused = false;

    const loop = () => {
      drawScene(ctx, performance.now() / 1000);
      raf = requestAnimationFrame(loop);
    };
    const update = () => {
      const shouldRun = !reduced.matches && !document.hidden && !wePaused;
      if (shouldRun && !running) { running = true; raf = requestAnimationFrame(loop); }
      if (!shouldRun && running) { running = false; cancelAnimationFrame(raf); }
      if (reduced.matches) drawScene(ctx, 0); // bevidst stillbillede
    };

    const onVisibility = () => update();
    document.addEventListener('visibilitychange', onVisibility);
    reduced.addEventListener('change', update);

    // Wallpaper Engine kalder setPaused når wallpaperet dækkes af et fuldskærmsprogram.
    const prevListener = window.wallpaperPropertyListener;
    window.wallpaperPropertyListener = {
      ...prevListener,
      setPaused: (isPaused) => { wePaused = isPaused; update(); },
    };

    update();
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('visibilitychange', onVisibility);
      reduced.removeEventListener('change', update);
      window.wallpaperPropertyListener = prevListener;
    };
  }, []);

  return <canvas ref={ref} className="amb-canvas" width={W} height={H} />;
}

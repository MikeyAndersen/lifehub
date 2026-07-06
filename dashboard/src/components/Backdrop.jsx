import { useEffect, useRef } from 'react';

/* Backdrop (DEL 2) — de to bagerste z-lag under cards:
   1. Nebula: store blurede radial-gradients (CSS, drift 65–90s, opacity ≤0.12).
   2. Partikler: ét canvas, max 80 partikler i 3 dybdelag med parallax-drift
      (dybe lag driver langsomst) og blød opacity-sinus-twinkle.
   Ingen libraries. Fryser som stillbillede ved prefers-reduced-motion og
   pauser når fanen er skjult — samme mønster som ambient/Wings.jsx. */

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* 36+27+15 = 78 partikler — under spec-loftet på 80. drift er px/minut. */
const LAYERS = [
  { n: 36, r: [0.5, 1.1], alpha: 0.14, drift: 1.6 },
  { n: 27, r: [0.8, 1.5], alpha: 0.22, drift: 3.4 },
  { n: 15, r: [1.1, 2.0], alpha: 0.32, drift: 6.0 },
];

function makeParticles() {
  const rnd = mulberry32(20260706);
  const ps = [];
  for (const L of LAYERS) {
    for (let i = 0; i < L.n; i++) {
      ps.push({
        x: rnd(), y: rnd(),
        r: L.r[0] + rnd() * (L.r[1] - L.r[0]),
        base: L.alpha * (0.6 + rnd() * 0.4),
        twinkle: rnd() < 0.35,
        dur: 6 + rnd() * 8,          // twinkle-periode 6–14s (langsom)
        phase: rnd() * 14,
        dx: (rnd() - 0.5) * 2 * L.drift,
        dy: (rnd() - 0.5) * 2 * L.drift,
      });
    }
  }
  return ps;
}

const PARTICLES = makeParticles();

function draw(ctx, w, h, t) {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#AFC0DC';
  for (const p of PARTICLES) {
    const x = (((p.x * w + (p.dx * t) / 60) % w) + w) % w;
    const y = (((p.y * h + (p.dy * t) / 60) % h) + h) % h;
    ctx.globalAlpha = p.twinkle
      ? p.base * (0.7 + 0.3 * Math.sin((2 * Math.PI * (t + p.phase)) / p.dur))
      : p.base;
    ctx.beginPath();
    ctx.arc(x, y, p.r, 0, 2 * Math.PI);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

export default function Backdrop() {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext('2d');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let raf = 0, running = false;

    const resize = () => {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      if (!running) draw(ctx, canvas.width, canvas.height, reduced.matches ? 0 : performance.now() / 1000);
    };

    const loop = () => {
      draw(ctx, canvas.width, canvas.height, performance.now() / 1000);
      raf = requestAnimationFrame(loop);
    };
    const update = () => {
      const shouldRun = !reduced.matches && !document.hidden;
      if (shouldRun && !running) { running = true; raf = requestAnimationFrame(loop); }
      if (!shouldRun && running) { running = false; cancelAnimationFrame(raf); }
      if (reduced.matches) draw(ctx, canvas.width, canvas.height, 0); // stillbillede
    };

    resize();
    update();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', update);
    reduced.addEventListener('change', update);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', update);
      reduced.removeEventListener('change', update);
    };
  }, []);

  return (
    <div className="backdrop" aria-hidden="true">
      <div className="nebula nebula-1" />
      <div className="nebula nebula-2" />
      <div className="nebula nebula-3" />
      <canvas ref={ref} className="backdrop-canvas" />
    </div>
  );
}

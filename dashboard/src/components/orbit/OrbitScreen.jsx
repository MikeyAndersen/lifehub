import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchAmbientEvents, fetchAmbientStats, fetchDashboard } from '../../lib/api.js';
import { startDaycycle } from '../../lib/daycycle.js';
import { fmtClock, fmtDateLine, fmtDay, fmtTime, p2 } from '../../lib/format.js';
import useCountUp from '../../lib/useCountUp.js';
import LivingPlanet from './LivingPlanet.jsx';

/* /ambient/orbit (DEL 5) — roligt mission control på 1920×1080.
   Central orb = en blød, dæmpet glød (aldrig en lysende sol), tynde
   orbit-ringe, korrektionsraten som tynd ring-gauge, 7b/32b som to måner
   hvis størrelse afspejler deres andel af kørsler, og stats i næsten
   usynlige glas-paneler — tallene og typografien bærer designet.
   Event-puls: nye sys_events spawner en partikel der langsomt kredser ind
   mod orben og absorberes med et blødt lysskifte (opacity-ease, 1.5s).
   Tal uden datagrundlag vises som "indsamler data…" — aldrig opfundet. */

const W = 1920, H = 1080, CX = 960, CY = 500;
const ABSORB_R = 128;

const KIND_LABELS = {
  'prompt': 'Prompt modtaget',
  'pass2:corrected': 'Kvalitetstjek — rettet',
  'pass2': 'Kvalitetstjek',
  'triage:aula': 'Aula-mail behandlet',
  'triage': 'Post triageret',
  'vikunja_write': 'Vikunja-opdatering',
};

const kindLabel = (ev) =>
  KIND_LABELS[`${ev.kind}:${ev.label}`] || KIND_LABELS[ev.kind] || ev.kind;

function useViewport() {
  const [size, setSize] = useState(null);
  useEffect(() => {
    const measure = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);
  return size;
}

/* Partikel-laget: ét canvas, rAF-loop med pause ved document.hidden.
   Ved prefers-reduced-motion springes animationen over — eventet
   "absorberes" direkte (lysskiftet/labelen dæmpes af den globale regel). */
function Particles({ queueRef, onAbsorb }) {
  const ref = useRef(null);
  const absorbRef = useRef(onAbsorb);
  absorbRef.current = onAbsorb;

  useEffect(() => {
    const ctx = ref.current.getContext('2d');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let parts = [], raf = 0, running = false, last = performance.now();

    const step = (t) => {
      const dt = Math.min(0.05, (t - last) / 1000);
      last = t;
      while (queueRef.current.length) {
        const ev = queueRef.current.shift();
        if (reduced.matches) {
          absorbRef.current(ev);
        } else {
          parts.push({
            ev,
            a: Math.random() * Math.PI * 2,
            r: 560 + Math.random() * 90,
            va: 0.18 + Math.random() * 0.08,   // rolig vinkelfart
            vr: 38,                             // px/s indad, vokser blidt
          });
        }
      }
      ctx.clearRect(0, 0, W, H);
      parts = parts.filter((p) => {
        p.a += p.va * dt;
        p.vr += 16 * dt;
        p.r -= p.vr * dt;
        if (p.r <= ABSORB_R) {
          absorbRef.current(p.ev);
          return false;
        }
        const x = CX + p.r * Math.cos(p.a);
        const y = CY + p.r * Math.sin(p.a);
        ctx.fillStyle = '#CBD8EC';
        ctx.globalAlpha = 0.16;
        ctx.beginPath(); ctx.arc(x, y, 6, 0, 2 * Math.PI); ctx.fill();
        ctx.globalAlpha = 0.5;
        ctx.beginPath(); ctx.arc(x, y, 2.3, 0, 2 * Math.PI); ctx.fill();
        return true;
      });
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(step);
    };
    const update = () => {
      const shouldRun = !document.hidden;
      if (shouldRun && !running) { running = true; last = performance.now(); raf = requestAnimationFrame(step); }
      if (!shouldRun && running) { running = false; cancelAnimationFrame(raf); }
    };
    update();
    document.addEventListener('visibilitychange', update);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('visibilitychange', update);
    };
  }, [queueRef]);

  return <canvas ref={ref} className="orbit-canvas" width={W} height={H} />;
}

function Stat({ label, value, unit, collecting }) {
  const n = useCountUp(typeof value === 'number' ? value : null);
  return (
    <div className="orbit-stat">
      <span className="orbit-stat-label">{label}</span>
      {collecting
        ? <span className="orbit-collecting">indsamler data…</span>
        : <span className="orbit-stat-value">{n}{unit && <span className="orbit-stat-unit"> {unit}</span>}</span>}
    </div>
  );
}

function Panel({ title, x, y, acc, children }) {
  return (
    <div className="orbit-panel" style={{ left: x, top: y, '--panel-acc': `var(--acc-${acc})` }}>
      <h3>{title}</h3>
      {children}
    </div>
  );
}

/* Korrektionsraten som tynd ring-gauge omkring orben. */
function Gauge({ rate }) {
  const R = 172, C = 2 * Math.PI * R;
  const shown = useCountUp(rate == null ? null : Math.round(rate * 1000) / 10, { decimals: 1 });
  if (rate == null) return null;
  return (
    <svg className="orbit-gauge" width={2 * R + 8} height={2 * R + 8} aria-hidden="true">
      <circle cx={R + 4} cy={R + 4} r={R} fill="none"
        stroke="rgba(148,163,190,0.08)" strokeWidth="2" />
      <circle cx={R + 4} cy={R + 4} r={R} fill="none"
        stroke="rgb(var(--tod-tint) / 0.4)" strokeWidth="2" strokeLinecap="round"
        strokeDasharray={`${C * rate} ${C}`}
        transform={`rotate(-90 ${R + 4} ${R + 4})`} />
      <text x={R + 4} y={R - 152} textAnchor="middle" className="orbit-gauge-text">
        {shown}% rettet
      </text>
    </svg>
  );
}

/* 7b/32b som to måner — størrelsen afspejler andelen af kørsler. */
function Moons({ models }) {
  const total = (models?.cpu_7b?.runs || 0) + (models?.gpu_32b?.runs || 0);
  const moons = [
    { key: '7b', deg: 148, runs: models?.cpu_7b?.runs || 0, name: '7b · CPU' },
    { key: '32b', deg: 24, runs: models?.gpu_32b?.runs || 0, name: '32b · GPU' },
  ];
  return moons.map((m) => {
    const share = total ? m.runs / total : 0.5;
    const size = 9 + 17 * share;
    const th = (m.deg * Math.PI) / 180;
    const x = CX + 300 * Math.cos(th), y = CY + 300 * Math.sin(th);
    return (
      <div key={m.key}>
        <div className="orbit-moon" style={{ left: x, top: y, width: size, height: size }} />
        <div className="orbit-moon-label" style={{ left: x, top: y + size / 2 + 8 }}>
          {m.name} · {m.runs}
        </div>
      </div>
    );
  });
}

export default function OrbitScreen() {
  const [stats, setStats] = useState(null);
  const [doc, setDoc] = useState(null);
  const [now, setNow] = useState(() => new Date());
  const [pulse, setPulse] = useState(0);
  const [labels, setLabels] = useState([]);
  const [hideCursor, setHideCursor] = useState(false);
  const queueRef = useRef([]);
  const lastIdRef = useRef(null);
  const labelIdRef = useRef(0);
  const size = useViewport();

  // Data-polling: stats 45s (matcher server-cachen), events 10s, feed 60s.
  useEffect(() => {
    const stopDaycycle = startDaycycle();
    const loadStats = () => fetchAmbientStats().then(setStats).catch(() => {});
    const loadDoc = () => fetchDashboard(true).then(setDoc).catch(() => {});
    const pollEvents = () =>
      fetchAmbientEvents(lastIdRef.current)
        .then((r) => {
          // Første svar sætter kun cursoren — historik skal ikke pulse.
          if (lastIdRef.current != null) {
            queueRef.current.push(...r.events.slice(-5));
          }
          lastIdRef.current = r.last_id;
        })
        .catch(() => {});
    loadStats(); loadDoc(); pollEvents();
    const ids = [
      setInterval(loadStats, 45_000),
      setInterval(loadDoc, 60_000),
      setInterval(pollEvents, 10_000),
      setInterval(() => setNow(new Date()), 1_000),
    ];
    return () => { ids.forEach(clearInterval); stopDaycycle(); };
  }, []);

  // Skjul cursoren efter 3 sekunders inaktivitet.
  useEffect(() => {
    let timer;
    const wake = () => {
      setHideCursor(false);
      clearTimeout(timer);
      timer = setTimeout(() => setHideCursor(true), 3_000);
    };
    wake();
    window.addEventListener('mousemove', wake);
    return () => { clearTimeout(timer); window.removeEventListener('mousemove', wake); };
  }, []);

  const onAbsorb = (ev) => {
    setPulse((p) => p + 1);
    const id = ++labelIdRef.current;
    const deg = 200 + (id % 5) * 32;              // spredte, deterministiske pladser
    setLabels((ls) => [...ls.slice(-3), { id, text: kindLabel(ev), deg }]);
    setTimeout(() => setLabels((ls) => ls.filter((l) => l.id !== id)), 3_400);
  };

  const nextEvent = useMemo(() => {
    const todayKey = `${now.getFullYear()}-${p2(now.getMonth() + 1)}-${p2(now.getDate())}`;
    return (doc?.events || []).find((e) =>
      e.all_day ? e.start.slice(0, 10) >= todayKey : new Date(e.start) >= now);
  }, [doc, now]);

  if (!size) return null;
  const fitScale = Math.min(size.w / W, size.h / H);
  const r = stats?.reviews;

  return (
    <div className={`orbit-viewport${hideCursor ? ' no-cursor' : ''}`}>
      <div className="orbit-stage" style={{ transform: `scale(${fitScale})` }}>
        {/* Tynde orbit-ringe + gauge + måner omkring orben */}
        {[464, 600].map((d) => (
          <div key={d} className="orbit-ring" style={{ width: d, height: d }} />
        ))}
        <Gauge rate={r?.correction_rate ?? null} />
        <Moons models={stats?.models} />

        {/* Levende planet i centrum: følger døgn + vejr, med diskret liv */}
        <LivingPlanet weather={doc?.weather} now={now} flashKey={pulse} />

        <Particles queueRef={queueRef} onAbsorb={onAbsorb} />

        {/* Diskrete event-labels der fader ud nær orben */}
        {labels.map((l) => {
          const th = (l.deg * Math.PI) / 180;
          return (
            <div key={l.id} className="orbit-event-label"
              style={{ left: CX + 195 * Math.cos(th), top: CY + 195 * Math.sin(th) }}>
              {l.text}
            </div>
          );
        })}

        {/* Svævende glas-paneler i orbit omkring orben */}
        <Panel title="Prompter" x={300} y={252} acc="tasks">
          <Stat label="I dag" value={stats?.prompts?.today}
            collecting={stats != null && stats.prompts?.today == null} />
          <Stat label="I alt" value={stats?.prompts?.total}
            collecting={stats != null && stats.prompts?.total == null} />
        </Panel>

        <Panel title="Dual-pass" x={1340} y={252} acc="calendar">
          <Stat label="7b-kørsler" value={r?.pass1_total} />
          <Stat label="32b-reviews" value={r?.pass2_total} />
          <Stat label="Rettet" value={r?.corrected}
            collecting={stats != null && r?.corrected == null} />
        </Panel>

        <Panel title="I dag" x={1340} y={622} acc="mail">
          <Stat label="Gmail-triage" value={stats?.triage?.today} />
          <Stat label="Vikunja-writes" value={stats?.vikunja?.writes_today}
            collecting={stats != null && stats.vikunja?.writes_today == null} />
        </Panel>

        <Panel title="Highlights" x={300} y={622} acc="weather">
          {(stats?.highlights?.length ?? 0) === 0 && (
            <span className="orbit-collecting">indsamler data…</span>
          )}
          {(stats?.highlights || []).map((h, i) => (
            <div className="orbit-highlight" key={i}>
              <span className="orbit-stat-label">{h.label}</span>
              <span className="orbit-highlight-value">
                {h.value}{h.detail ? <span className="orbit-stat-unit"> · {h.detail}</span> : null}
              </span>
            </div>
          ))}
        </Panel>

        {/* Bund: stort ur + næste kalender-event i tynd typografi */}
        <div className="orbit-bottom">
          <div className="orbit-clock">{fmtClock(now)}</div>
          <div className="orbit-date">{fmtDateLine(now, true)}</div>
          <div className="orbit-next">
            {nextEvent
              ? `Næste: ${nextEvent.all_day
                  ? `${fmtDay(nextEvent.start)} · hele dagen`
                  : `${fmtDay(nextEvent.start)} ${fmtTime(nextEvent.start)}`} — ${nextEvent.title}`
              : 'Ingen kommende aftaler'}
          </div>
        </div>
      </div>
    </div>
  );
}

import { fmtClock, fmtDateLine, fmtTime, isoWeek, p2 } from '../../lib/format.js';

/* Orbit-uret — signaturelementet. En 24-timers skive med midnat øverst:
   dagens aftaler er "planeter" placeret efter klokkeslæt. Kommende aftaler
   glider fra yderringen (r=310) mod inderringen (r=240) over de sidste 4
   timer; overståede ligger dæmpede på inderringen. */

const CX = 390, CY = 390, R_OUTER = 310, R_INNER = 240;

/** Position på skiven for et klokkeslæt (decimaltimer) og en radius. */
function pos(hours, r) {
  const th = (hours / 24) * Math.PI * 2;
  return { x: CX + r * Math.sin(th), y: CY - r * Math.cos(th), deg: (hours / 24) * 360 };
}

const HOUR_MARKS = [0, 6, 12, 18].map((h) => ({ label: p2(h), ...pos(h, 352) }));

export default function OrbitClock({ now, events }) {
  const nowH = now.getHours() + now.getMinutes() / 60;
  const tick = pos(nowH, R_OUTER);

  const planets = events.map((e) => {
    const h = +e.start.slice(11, 13) + e.start.slice(14, 16) / 60;
    const until = h - nowH;
    const past = until < 0;
    const r = past ? R_INNER : R_OUTER - 70 * Math.max(0, Math.min(1, 1 - until / 4));
    return { ...pos(h, r), label: pos(h, r + 62), past, time: fmtTime(e.start), title: e.title };
  });

  return (
    <div className="amb-dial">
      <div className="amb-dial-ring-outer" />
      <div className="amb-dial-ring-inner" />
      {HOUR_MARKS.map((m) => (
        <div className="amb-hourmark" key={m.label} style={{ left: m.x, top: m.y }}>{m.label}</div>
      ))}
      <div
        className="amb-nowtick"
        style={{ left: tick.x, top: tick.y, transform: `translate(-50%,-50%) rotate(${tick.deg}deg)` }}
      />
      {planets.map((planet, i) => (
        <div key={i} style={{ opacity: planet.past ? 0.35 : 1 }}>
          <div
            className="amb-planet"
            style={{
              left: planet.x,
              top: planet.y,
              width: planet.past ? 10 : 13,
              height: planet.past ? 10 : 13,
              background: planet.past ? 'var(--lh-text-3)' : 'var(--lh-signal)',
              boxShadow: planet.past ? 'none' : '0 0 14px rgba(240,162,46,0.5)',
            }}
          />
          <div
            className={`amb-planet-label${planet.past ? ' past' : ''}`}
            style={{ left: planet.label.x, top: planet.label.y }}
          >
            <div className="amb-planet-time">{planet.time}</div>
            <div className="amb-planet-title">{planet.title}</div>
          </div>
        </div>
      ))}
      <div className="amb-dial-center">
        <div className="amb-clock">{fmtClock(now)}</div>
        <div className="amb-date">{fmtDateLine(now, true)}</div>
        <div className="amb-week">uge {isoWeek(now)}</div>
      </div>
    </div>
  );
}

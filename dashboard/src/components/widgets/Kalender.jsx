import Card from './Card.jsx';
import { fmtTime, fmtDayGroupLabel } from '../../lib/format.js';

function groupByDay(events) {
  const groups = [];
  for (const e of events) {
    const key = e.start.slice(0, 10);
    let g = groups.find((g) => g.key === key);
    if (!g) groups.push((g = { key, first: e.start, events: [] }));
    g.events.push(e);
  }
  return groups;
}

/* Overlap-layout (DEL 4): tidsatte events uden sluttid antages 60 min.
   Events der overlapper i tid samles i klustre; hvert kluster fordeles
   grådigt i N kolonner (første kolonne hvis seneste event er slut).
   Solo-events beholder fuld bredde. */
const ASSUMED_MIN = 60;

function span(e) {
  const start = new Date(e.start).getTime();
  const rawEnd = e.end ? new Date(e.end).getTime() : start + ASSUMED_MIN * 60000;
  return { start, end: Math.max(rawEnd, start + 15 * 60000) }; // min 15 min
}

function clusterTimed(events) {
  const timed = events
    .filter((e) => !e.all_day)
    .map((e) => ({ e, ...span(e) }))
    .sort((a, b) => a.start - b.start);

  const clusters = [];
  let current = null;
  for (const it of timed) {
    if (current && it.start < current.end) {
      current.items.push(it);
      current.end = Math.max(current.end, it.end);
    } else {
      clusters.push((current = { items: [it], end: it.end }));
    }
  }
  // Kolonnefordeling pr. kluster: første kolonne hvis seneste event er slut.
  for (const c of clusters) {
    const colEnds = [];
    for (const it of c.items) {
      let col = colEnds.findIndex((end) => end <= it.start);
      if (col === -1) col = colEnds.length;
      colEnds[col] = it.end;
      it.col = col;
    }
    c.cols = colEnds.length;
  }
  return clusters;
}

function tooltip(e) {
  const time = e.all_day ? 'hele dagen' : fmtTime(e.start) + (e.end ? `–${fmtTime(e.end)}` : '');
  return [time, e.title, e.location].filter(Boolean).join(' · ');
}

/* Kalender — næste 7 dage, grupperet pr. dag. */
export default function Kalender({ events = [] }) {
  const groups = groupByDay(events.slice(0, 12));
  return (
    <Card label="Kalender" accent="calendar" primary pulseKey={JSON.stringify(events)}>
      {groups.length === 0 && <p className="muted">Ingen aftaler — nyd friheden.</p>}
      <div className="day-groups">
        {groups.map((g) => {
          const allDay = g.events.filter((e) => e.all_day);
          const clusters = clusterTimed(g.events);
          return (
            <div key={g.key}>
              <div className="day-label">{fmtDayGroupLabel(g.first)}</div>
              <div>
                {allDay.map((e, i) => (
                  <div className="ev-row" key={`ad${i}`} title={tooltip(e)}>
                    <span className="ev-time">—</span>
                    <span className="ev-title">
                      {e.title}
                      {e.location && <div className="ev-loc">{e.location}</div>}
                    </span>
                  </div>
                ))}
                {clusters.map((c, ci) =>
                  c.cols === 1 ? (
                    c.items.map((it, i) => (
                      <div className="ev-row" key={`${ci}-${i}`} title={tooltip(it.e)}>
                        <span className="ev-time">{fmtTime(it.e.start)}</span>
                        <span className="ev-title">
                          {it.e.title}
                          {it.e.location && <div className="ev-loc">{it.e.location}</div>}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div
                      className="ev-cluster"
                      key={ci}
                      style={{ gridTemplateColumns: `repeat(${c.cols}, minmax(0, 1fr))` }}
                    >
                      {c.items.map((it, i) => (
                        <div
                          className="ev-chip"
                          key={i}
                          style={{ gridColumn: it.col + 1 }}
                        >
                          <span className="ev-chip-time">{fmtTime(it.e.start)}</span>
                          <span className="ev-chip-title">{it.e.title}</span>
                          <span className="ev-tip" role="tooltip">{tooltip(it.e)}</span>
                        </div>
                      ))}
                    </div>
                  ),
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

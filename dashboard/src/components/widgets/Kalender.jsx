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

/* Kalender — næste 7 dage, grupperet pr. dag. */
export default function Kalender({ events = [] }) {
  const groups = groupByDay(events.slice(0, 12));
  return (
    <Card label="Kalender">
      {groups.length === 0 && <p className="muted">Ingen aftaler — nyd friheden.</p>}
      <div className="day-groups">
        {groups.map((g) => (
          <div key={g.key}>
            <div className="day-label">{fmtDayGroupLabel(g.first)}</div>
            <div>
              {g.events.map((e, i) => (
                <div className="ev-row" key={i}>
                  <span className="ev-time">{e.all_day ? '—' : fmtTime(e.start)}</span>
                  <span className="ev-title">
                    {e.title}
                    {e.location && <div className="ev-loc">{e.location}</div>}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

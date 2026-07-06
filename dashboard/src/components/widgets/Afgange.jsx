import Card from './Card.jsx';
import { fmtTime, fmtRel } from '../../lib/format.js';

/* Afgange — fase 2-blok (transit); skjules helt når blokken mangler. */
export default function Afgange({ transit, now }) {
  if (!transit) return null;
  const meta = transit.station && (
    <span className="card-meta">
      {transit.station}{transit.direction ? ` → ${transit.direction}` : ''}
    </span>
  );
  const upcoming = (transit.departures || []).filter((iso) => new Date(iso) >= now);
  return (
    <Card label="Afgange" pulseKey={JSON.stringify(transit.departures)} meta={meta}>
      {(transit.status === 'not_configured' || upcoming.length === 0) && (
        <p className="muted">Afgangsdata er ikke koblet til endnu.</p>
      )}
      {upcoming.slice(0, 3).map((iso, i) => (
        <div className="dep-row" key={i}>
          <span className="dep-time">{fmtTime(iso)}</span>
          <span className="dep-rel">{fmtRel(iso, now)}</span>
        </div>
      ))}
    </Card>
  );
}

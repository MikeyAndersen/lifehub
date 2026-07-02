import Card from './Card.jsx';

/* Middag i aften — fase 2-blok (madplan); skjules helt når blokken mangler. */
export default function Middag({ madplan }) {
  if (!madplan) return null;
  if (madplan.status === 'not_configured' || !madplan.tonight) {
    return (
      <Card label="Middag i aften">
        <p className="muted">Madplanen er ikke koblet til endnu.</p>
      </Card>
    );
  }
  const { dish, cook, note } = madplan.tonight;
  return (
    <Card label="Middag i aften">
      <div className="dinner-dish">{dish}</div>
      {cook && <div className="dinner-cook">{cook}</div>}
      {note && <div className="dinner-note">{note}</div>}
    </Card>
  );
}

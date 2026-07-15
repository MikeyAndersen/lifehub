import Card from './Card.jsx';

const LABELS = { koleskab: 'Køleskab', fryser: 'Fryser', skab: 'Skab', ovrigt: 'Øvrigt' };
const ORDER = ['koleskab', 'fryser', 'skab', 'ovrigt'];

/* Beholdning (Feature B) — kompakt liste grupperet på lokation. Skjules helt
   når blokken mangler. `stale` = gemt kopi vist fordi madplan var utilgængelig. */
export default function Beholdning({ beholdning }) {
  if (!beholdning || !beholdning.items?.length) return null;
  const groups = {};
  for (const it of beholdning.items) {
    const key = LABELS[it.category] ? it.category : 'ovrigt';
    (groups[key] ??= []).push(it);
  }
  const meta = beholdning.stale ? <span className="card-meta">gemt kopi</span> : null;
  return (
    <Card label="Beholdning" pulseKey={JSON.stringify(beholdning.items)} meta={meta}>
      {ORDER.filter((loc) => groups[loc]?.length).map((loc) => (
        <div className="inv-group" key={loc}>
          <div className="inv-loc mono">{LABELS[loc]} · {groups[loc].length}</div>
          <div className="inv-items">
            {groups[loc].slice(0, 8).map((it) => (
              <span className="inv-item" key={it.id}>
                {it.name}{it.quantity > 1 ? ` ×${it.quantity}` : ''}
              </span>
            ))}
            {groups[loc].length > 8 && (
              <span className="inv-item inv-more">+{groups[loc].length - 8}</span>
            )}
          </div>
        </div>
      ))}
    </Card>
  );
}

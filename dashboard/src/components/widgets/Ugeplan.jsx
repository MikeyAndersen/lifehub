import Card from './Card.jsx';
import { p2 } from '../../lib/format.js';

const WDS = ['Søn', 'Man', 'Tir', 'Ons', 'Tor', 'Fre', 'Lør'];

const todayKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
};

/* Ugeplan — 7 dage med i dag fremhævet (fase 2-madplan). Skjules helt når
   blokken mangler. `stale` = seneste cache vist fordi madplan var utilgængelig. */
export default function Ugeplan({ madplan }) {
  if (!madplan || !madplan.days?.length) return null;
  const tk = todayKey();
  const meta = madplan.stale ? <span className="card-meta">gemt kopi</span> : null;
  return (
    <Card label="Ugeplan" pulseKey={JSON.stringify(madplan.days)} meta={meta}>
      <div className="wp-list">
        {madplan.days.map((d) => {
          const today = d.date === tk;
          const wd = WDS[new Date(`${d.date}T00:00:00`).getDay()];
          return (
            <div className={`wp-row${today ? ' today' : ''}`} key={d.date}>
              <span className="wp-day mono">{wd}</span>
              <span className={`wp-dish${d.dish_name ? '' : ' empty'}`}>
                {d.dish_name || '—'}
              </span>
              {d.status === 'cooked' && <span className="wp-check" title="lavet">✓</span>}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

import Card from './Card.jsx';
import { p2 } from '../../lib/format.js';

const WDS = ['Søn', 'Man', 'Tir', 'Ons', 'Tor', 'Fre', 'Lør'];

/* Offentlig madplan-base til opskrift-links. Samme env-mønster som PUBLIC_API_BASE. */
const MADPLAN_BASE = import.meta.env.PUBLIC_MADPLAN_BASE || 'https://madplan.nova-tech.dk';

/* Åben kogebog — markerer at retten har en bundet opskrift og kan klikkes. */
const RecipeIcon = () => (
  <svg className="wp-recipe-icon" width="13" height="13" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
       aria-hidden="true">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const todayKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
};

/* Ugeplan — 7 dage med i dag fremhævet (fase 2-madplan). Skjules helt når
   blokken mangler. `stale` = seneste cache vist fordi madplan var utilgængelig.
   Kort-titlen linker til madplan-forsiden; retter med bundet opskrift linker
   til selve opskriften og markeres med et kogebogs-ikon. */
export default function Ugeplan({ madplan }) {
  if (!madplan || !madplan.days?.length) return null;
  const tk = todayKey();
  const meta = madplan.stale ? <span className="card-meta">gemt kopi</span> : null;
  const label = (
    <a className="wp-home" href={MADPLAN_BASE} target="_blank" rel="noopener noreferrer"
       title="Åbn madplan">
      Ugeplan
      <svg className="wp-home-arrow" width="11" height="11" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
           strokeLinejoin="round" aria-hidden="true">
        <path d="M7 17 17 7M9 7h8v8" />
      </svg>
    </a>
  );
  return (
    <Card label={label} pulseKey={JSON.stringify(madplan.days)} meta={meta}>
      <div className="wp-list">
        {madplan.days.map((d) => {
          const today = d.date === tk;
          const wd = WDS[new Date(`${d.date}T00:00:00`).getDay()];
          // Har retten en bundet opskrift, gøres navnet til et link mod madplan
          // og markeres med et ikon; ellers ren tekst (ikke klikbar).
          const dish = d.recipe_id ? (
            <a className="wp-dish wp-recipe" href={`${MADPLAN_BASE}/opskrifter/${d.recipe_id}`}
               target="_blank" rel="noopener noreferrer" title="Åbn opskrift">
              <span className="wp-dish-name">{d.dish_name}</span>
              <RecipeIcon />
            </a>
          ) : (
            <span className={`wp-dish${d.dish_name ? '' : ' empty'}`}>
              {d.dish_name || '—'}
            </span>
          );
          return (
            <div className={`wp-row${today ? ' today' : ''}`} key={d.date}>
              <span className="wp-day mono">{wd}</span>
              {dish}
              {d.status === 'cooked' && <span className="wp-check" title="lavet">✓</span>}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

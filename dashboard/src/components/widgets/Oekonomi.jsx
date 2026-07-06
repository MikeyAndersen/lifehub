import Card from './Card.jsx';
import { fmtKr, fmtBdDate } from '../../lib/format.js';
import useCountUp from '../../lib/useCountUp.js';

function Amount({ value }) {
  return <span className="amount">{fmtKr(useCountUp(value))}</span>;
}

/* Økonomi — kun i det interaktive dokument, og kun for admin-brugere.
   Blokken mangler helt for andre; kortet skjules så uden layout-hul
   (kort-flowet er flex-wrap). */
export default function Oekonomi({ finance, onHide }) {
  return (
    <Card
      label="Økonomi"
      chip="privat"
      pulseKey={JSON.stringify(finance)}
      meta={<button className="linkish" style={{ fontSize: 12 }} onClick={onHide}>Skjul</button>}
    >
      {finance.status === 'not_configured' && (
        <p className="muted">Banktilslutning er ikke sat op endnu (GoCardless) — viser noterede udgifter.</p>
      )}
      {(finance.accounts || []).map((a, i) => (
        <div className="acct-row" key={i}>
          <span className="acct-name">{a.name}</span>
          <Amount value={a.balance_dkk} />
        </div>
      ))}
      {finance.recent_expenses?.length > 0 && (
        <div className="exp-section">
          <div className="exp-label">Seneste</div>
          {finance.recent_expenses.slice(0, 3).map((e, i) => (
            <div className="exp-row" key={i}>
              <span className="exp-name">
                {e.title}
                {e.noted_at && <span style={{ color: 'var(--lh-text-3)' }}> · {fmtBdDate(e.noted_at)}</span>}
              </span>
              <span className="exp-amount">−{fmtKr(e.amount_dkk)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

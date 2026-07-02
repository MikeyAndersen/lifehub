import Card from './Card.jsx';
import { fmtBdDate } from '../../lib/format.js';

/* Fødselsdage — næste 30 dage. */
export default function Foedselsdage({ birthdays = [] }) {
  return (
    <Card label="Fødselsdage" meta={<span className="card-meta">næste 30 dage</span>}>
      {birthdays.length === 0 && <p className="muted">Ingen fødselsdage lige nu.</p>}
      {birthdays.map((b, i) => (
        <div className="bd-row" key={i}>
          <span className="bd-date">{fmtBdDate(b.date)}</span>
          <span className="bd-name">{b.title}</span>
        </div>
      ))}
    </Card>
  );
}

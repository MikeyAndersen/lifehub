import Card from './Card.jsx';
import { fmtDay } from '../../lib/format.js';
import useCountUp from '../../lib/useCountUp.js';

/* Aula — info fra skolen (7 dage) + forslag/auto-oprettelser med status.
   Al tekst er mail-udledt: React escaper by default, ingen rå HTML her. */
const STATUS_LABEL = {
  pending: 'afventer',
  approved: 'oprettet',
  auto_created: 'auto-oprettet',
  edited: 'redigeret',
  rejected: 'afvist',
  expired: 'udløbet',
  undone: 'fortrudt',
  notified: 'sendt',
  briefed: '',
};

export default function Aula({ aula }) {
  const newToday = useCountUp(aula?.new_today ?? 0);
  if (!aula) return null;
  const info = aula.info || [];
  const actions = (aula.recent || []).slice(0, 6);
  if (info.length === 0 && actions.length === 0) return null;

  return (
    <Card
      label="Aula"
      accent="mail"
      pulseKey={JSON.stringify(aula)}
      meta={aula.new_today > 0 && (
        <span className="card-meta">{newToday} nye i dag</span>
      )}
    >
      {actions.map((a, i) => (
        <div className="task-row" key={`a${i}`}>
          <span className="task-box">{a.intent === 'event' ? '📅' : '☑️'}</span>
          <span className="task-title">
            {a.title}
            {STATUS_LABEL[a.status] && (
              <span className="muted"> · {STATUS_LABEL[a.status]}</span>
            )}
          </span>
          <span className="task-due">{a.date ? fmtDay(a.date) : ''}</span>
        </div>
      ))}
      {info.length > 0 && (
        <>
          <div className="day-label">Info fra Aula</div>
          {info.slice(0, 6).map((it, i) => (
            <div className="task-row" key={`i${i}`}>
              <span className="task-box">📧</span>
              <span className="task-title">{it.title}</span>
              <span className="task-due">{fmtDay(it.created_at)}</span>
            </div>
          ))}
        </>
      )}
    </Card>
  );
}

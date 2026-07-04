import { useState } from 'react';
import Card from './Card.jsx';
import { setTaskDone } from '../../lib/api.js';
import { fmtDue, fmtDoneAt, isOverdue } from '../../lib/format.js';

/* Opgaver — afkrydsning skriver tilbage til Vikunja via brain.
   Optimistisk update; rulles tilbage hvis kaldet fejler.
   Knappen nederst folder opgaver afkrydset de seneste 48 timer ud. */
export default function Opgaver({ tasks = [], doneTasks = [] }) {
  const [done, setDone] = useState({});
  const [pending, setPending] = useState({});
  const [error, setError] = useState(null);
  const [showDone, setShowDone] = useState(false);

  const toggle = async (id) => {
    if (pending[id]) return;
    const next = !done[id];
    setDone((s) => ({ ...s, [id]: next }));
    setPending((s) => ({ ...s, [id]: true }));
    setError(null);
    try {
      await setTaskDone(id, next);
    } catch {
      setDone((s) => ({ ...s, [id]: !next }));
      setError('Kunne ikke opdatere opgaven i Vikunja — prøv igen.');
    } finally {
      setPending((s) => ({ ...s, [id]: false }));
    }
  };

  const open = tasks.filter((t) => !done[t.id]).length;

  return (
    <Card label="Opgaver" meta={<span className="card-meta">{open} åbne</span>}>
      {tasks.length === 0 && <p className="muted">Alt er gjort. Imponerende.</p>}
      {tasks.slice(0, 10).map((t) => {
        const isDone = !!done[t.id];
        const overdue = !isDone && isOverdue(t.due);
        return (
          <div
            key={t.id}
            className={`task-row${isDone ? ' done' : ''}${overdue ? ' overdue' : ''}`}
            onClick={() => toggle(t.id)}
          >
            <span className="task-box">{isDone ? '✓' : ''}</span>
            <span className="task-title">{t.title}</span>
            <span className="task-due">
              {overdue && <span className="task-dot" />}
              {t.due ? fmtDue(t.due) : <span className="muted">uden dato</span>}
            </span>
          </div>
        );
      })}
      {error && <p className="muted">{error}</p>}

      <button className="linkish" onClick={() => setShowDone((v) => !v)}>
        {showDone ? 'Skjul afkrydsede' : `Vis afkrydsede (${doneTasks.length})`}
      </button>
      {showDone && doneTasks.length === 0 && (
        <p className="muted">Ingen afkrydsede de seneste 48 timer.</p>
      )}
      {showDone && doneTasks.map((t) => (
        <div key={t.id} className="task-row done">
          <span className="task-box">✓</span>
          <span className="task-title">{t.title}</span>
          <span className="task-due">{fmtDoneAt(t.done_at)}</span>
        </div>
      ))}
    </Card>
  );
}

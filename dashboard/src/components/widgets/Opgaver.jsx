import { useState } from 'react';
import Card from './Card.jsx';
import { fmtDue, isOverdue } from '../../lib/format.js';

/* Opgaver — afkrydsning er kun lokal sessionstilstand (API'et er læse-eneste). */
export default function Opgaver({ tasks = [] }) {
  const [done, setDone] = useState({});
  const toggle = (id) => setDone((s) => ({ ...s, [id]: !s[id] }));
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
              {t.due ? fmtDue(t.due) : ''}
            </span>
          </div>
        );
      })}
    </Card>
  );
}

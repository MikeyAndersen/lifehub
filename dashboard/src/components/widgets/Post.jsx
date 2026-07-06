import Card from './Card.jsx';
import { fmtDay, fmtDue } from '../../lib/format.js';
import useCountUp from '../../lib/useCountUp.js';

/* Post — generel post-triage (Del 4). Admin-only: serveren udelader blokken
   for alle andre, så `!post` er det normale tilfælde. Al tekst er
   mail-udledt: React escaper by default, ingen rå HTML her. */
const STATUS_LABEL = {
  pending: 'afventer',
  approved: 'oprettet',
  edited: 'redigeret',
  rejected: 'afvist',
  expired: 'udløbet',
  notified: 'sendt',
  briefed: '',
};

export default function Post({ post }) {
  const newToday = useCountUp(post?.new_today ?? 0);
  if (!post) return null;
  const info = post.info || [];
  const actions = (post.recent || []).slice(0, 6);
  if (info.length === 0 && actions.length === 0) return null;

  return (
    <Card
      label="Post"
      accent="mail"
      pulseKey={JSON.stringify(post)}
      meta={post.new_today > 0 && (
        <span className="card-meta">{newToday} nye i dag</span>
      )}
    >
      {actions.map((a, i) => (
        <div className="task-row" key={`a${i}`}>
          <span className="task-box">{a.importance === 'high' ? '⚠️' : '☑️'}</span>
          <span className="task-title">
            {a.title}
            {STATUS_LABEL[a.status] && (
              <span className="muted"> · {STATUS_LABEL[a.status]}</span>
            )}
          </span>
          <span className="task-due">{a.deadline ? fmtDue(a.deadline) : ''}</span>
        </div>
      ))}
      {info.length > 0 && (
        <>
          <div className="day-label">Vigtig post</div>
          {info.slice(0, 6).map((it, i) => (
            <div className="task-row" key={`i${i}`}>
              <span className="task-box">{it.importance === 'high' ? '⚠️' : '📮'}</span>
              <span className="task-title">
                {it.title}
                {it.sender_kind && <span className="muted"> · {it.sender_kind}</span>}
              </span>
              <span className="task-due">{fmtDay(it.created_at)}</span>
            </div>
          ))}
        </>
      )}
    </Card>
  );
}

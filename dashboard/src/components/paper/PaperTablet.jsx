/* Warm Paper familie-dashboard (mockup 1d dag / 1e nat). Ren visning —
   ingen handlinger. Nat efter solnedgang: I MORGEN i stedet for I DAG. */
import { usePaperData } from './usePaperData.js';
import { isNight } from './paperNight.js';
import { pickHighlights, tomorrowOverview, classBadge, stripEmoji, dueLine } from './paperLogic.js';
import { fmtClock, weatherLabel } from '../../lib/format.js';
import WeatherIcon from './WeatherIcon.jsx';

const Label = ({ children, accent, right }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
    <div className="paper-mono" style={{ fontSize: 24, color: accent ? 'var(--accent)' : 'var(--muted)' }}>
      {children}
    </div>
    {right != null && <div className="paper-mono" style={{ fontSize: 24, color: 'var(--faint)' }}>{right}</div>}
  </div>
);

function TaskRow({ task, now, last }) {
  const due = task.due && dueLine(task.due, now);
  const urgent = due && (due.startsWith('i dag') || due === 'forfalden');
  return (
    <div style={{ display: 'flex', gap: 26, alignItems: 'center', padding: '22px 0',
                  borderBottom: last ? 'none' : '1px solid var(--hairline)' }}>
      <div className="paper-dot" style={{ width: 30, height: 30,
        border: `3px solid ${urgent ? 'var(--accent)' : 'var(--circle-idle)'}` }} />
      <div style={{ fontSize: 36, fontWeight: 500 }}>{stripEmoji(task.title)}</div>
      {urgent && <div className="paper-mono" style={{ fontSize: 22, color: 'var(--accent)', marginLeft: 'auto' }}>
        {due === 'forfalden' ? 'forfalden' : `inden ${task.due.slice(11, 16)}`}
      </div>}
    </div>
  );
}

function DoneRow({ task }) {
  return (
    <div style={{ display: 'flex', gap: 26, alignItems: 'center', padding: '22px 0' }}>
      <div className="paper-dot" style={{ width: 30, height: 30, background: 'var(--done-fill)',
        color: 'var(--paper-bg)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 20, fontWeight: 700 }}>✓</div>
      <div style={{ fontSize: 36, fontWeight: 500, color: 'var(--faint)',
                    textDecoration: 'line-through' }}>{stripEmoji(task.title)}</div>
    </div>
  );
}

export default function PaperTablet() {
  const { doc, error, now } = usePaperData(false);
  if (!doc) return <div className="paper-root" />;

  const night = isNight(now, doc.weather);
  const w = doc.weather;
  const dateLine = now.toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });
  const weatherLine = w
    ? `${weatherLabel(w.code).charAt(0).toUpperCase() + weatherLabel(w.code).slice(1)}` +
      (night && w.sunrise ? ` — solopgang kl. ${w.sunrise.slice(11, 16).replace(':', '.')}` : '')
    : '';

  const highlights = night ? null : pickHighlights(doc, now);
  const tomorrow = night ? tomorrowOverview(doc, now) : null;
  const tasks = night ? tomorrow.tasks : (doc.tasks || []).slice(0, 4);
  const lastDone = !night && (doc.tasks_done || [])[0];
  const shopping = (doc.shopping?.items || []).slice(0, 8);
  const aulaRows = [...(doc.aula?.info || []), ...(doc.aula?.recent || [])].slice(0, 3);

  return (
    <div className="paper-root" data-mode={night ? 'night' : 'day'}
         style={{ padding: '110px 120px', display: 'grid',
                  gridTemplateColumns: '1.05fr 1fr', gap: 140 }}>
      {/* — venstre: hero — */}
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div className="paper-clock" style={{ fontSize: 400, fontWeight: 600,
             letterSpacing: '-0.045em', lineHeight: 0.95 }}>{fmtClock(now)}</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 40, marginTop: 52 }}>
          <div style={{ fontSize: 62, fontWeight: 600, letterSpacing: '-0.015em',
                        color: night ? 'var(--ink-2)' : 'var(--ink)' }}>{dateLine}</div>
          {w && <div style={{ fontSize: 62, fontWeight: 400, color: 'var(--muted)' }}>
            {Math.round(w.now_c)}°</div>}
        </div>
        {error ? (
          <div className="paper-mono" style={{ fontSize: 24, color: 'var(--faint)', marginTop: 14 }}>
            opdateret {doc.generated_at?.slice(11, 16)} · offline
          </div>
        ) : (
          <div style={{ fontSize: 38, color: 'var(--muted)', marginTop: 14,
                        display: 'flex', alignItems: 'center', gap: 18 }}>
            {w && <WeatherIcon code={w.code} size={46} strokeWidth={1.5} />}
            <span>{weatherLine}</span>
          </div>
        )}
        <div style={{ marginTop: 'auto' }}>
          <div className="paper-mono" style={{ fontSize: 24, color: 'var(--accent)' }}>
            {night ? 'I MORGEN' : 'I DAG'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 36, marginTop: 32 }}>
            {night ? (
              <div style={{ display: 'flex', gap: 30, alignItems: 'baseline' }}>
                <div className="paper-dot" style={{ width: 16, height: 16,
                  border: '3px solid var(--accent)', transform: 'translateY(-6px)' }} />
                <div style={{ fontSize: 56, fontWeight: 600, lineHeight: 1.2,
                              color: 'var(--ink-2)' }}>{tomorrow.line}</div>
              </div>
            ) : highlights.map((h, i) => (
              <div key={i} style={{ display: 'flex', gap: 30, alignItems: 'baseline' }}>
                <div className="paper-dot" style={{ width: 16, height: 16, flex: 'none',
                  transform: 'translateY(-6px)',
                  ...(h.urgent ? { background: 'var(--accent)' }
                              : { border: '3px solid var(--accent)' }) }} />
                <div style={{ fontSize: 56, fontWeight: 600, lineHeight: 1.2,
                              letterSpacing: '-0.01em',
                              color: i === 0 ? 'var(--ink)' : 'var(--ink-2)' }}>{h.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {/* — højre kolonne bag hairline — */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 70,
                    borderLeft: '1px solid var(--hairline-strong)', paddingLeft: 110,
                    opacity: 'var(--side-opacity)' }}>
        <div>
          <Label right={tasks.length}>{night ? 'OPGAVER I MORGEN' : 'OPGAVER'}</Label>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 20 }}>
            {tasks.map((t, i) => (
              <TaskRow key={t.id} task={t} now={now}
                       last={i === tasks.length - 1 && !lastDone} />
            ))}
            {lastDone && <DoneRow task={lastDone} />}
          </div>
        </div>
        {!night && shopping.length > 0 && (
          <div>
            <Label>INDKØB</Label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px 18px', marginTop: 24 }}>
              {shopping.map((s) => (
                <div key={s.id} className="paper-pill" style={{ fontSize: 32, padding: '12px 26px' }}>
                  {stripEmoji(s.title)}
                </div>
              ))}
            </div>
          </div>
        )}
        <div>
          <Label>AULA</Label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 30, marginTop: 24 }}>
            {aulaRows.map((a, i) => {
              const badge = classBadge(a.title);
              return (
                <div key={i} style={{ display: 'flex', gap: 24, alignItems: 'baseline' }}>
                  <div className={`paper-badge${badge ? '' : ' paper-badge--neutral'}`}
                       style={{ fontSize: 24, flex: 'none' }}>{badge || 'AULA'}</div>
                  <div style={{ fontSize: 34, lineHeight: 1.35,
                                color: night ? 'var(--ink-2)' : 'var(--ink)' }}>
                    {stripEmoji(a.title)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

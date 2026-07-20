/* Warm Paper handlingspanel (mockup 1g, 1920×1080). Eneste interaktive
   paper-flade: indbakke-piller kalder brain-endpoints optimistisk — rækken
   fader ud med det samme og genindsættes med en stille notits ved fejl. */
import { useEffect, useState } from 'react';
import { usePaperData } from './usePaperData.js';
import { isNight } from './paperNight.js';
import { fetchPanelStatus, postTriageAction, archiveNewsletters } from '../../lib/api.js';
import { partitionInbox, postBadge, primaryAction, quietAction, dueLine,
         classBadge, stripEmoji } from './paperLogic.js';
import { fmtClock } from '../../lib/format.js';

const SectionLabel = ({ children, right }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
    <div className="paper-mono" style={{ fontSize: 14, color: 'var(--muted)' }}>{children}</div>
    {right != null && <div className="paper-mono" style={{ fontSize: 14, color: 'var(--faint)' }}>{right}</div>}
  </div>
);

function InboxRow({ item, onAction, failed }) {
  const badge = postBadge(item);
  const prim = primaryAction(item);
  const quiet = quietAction(item);
  return (
    <div style={{ padding: '18px 0', borderBottom: '1px solid var(--hairline)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: 18, fontWeight: 700 }}>{stripEmoji(item.title)}</div>
        <div className={`paper-badge${badge.tone === 'neutral' ? ' paper-badge--neutral' : ''}`}
             style={{ fontSize: 12 }}>{badge.label}</div>
      </div>
      {item.summary && <div style={{ fontSize: 17, color: 'var(--ink-2)', marginTop: 4 }}>
        {stripEmoji(item.summary)}</div>}
      <div style={{ display: 'flex', gap: 12, marginTop: 12, alignItems: 'center' }}>
        <button onClick={() => onAction(item, prim.action)} className="paper-pill"
                style={{ fontSize: 15, fontWeight: 600, color: 'var(--accent)',
                         borderColor: 'var(--accent)', padding: '6px 18px',
                         background: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
          {prim.label}
        </button>
        <button onClick={() => onAction(item, quiet.action)}
                style={{ fontSize: 15, fontWeight: 500, color: 'var(--muted)', padding: '6px 12px',
                         background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
          {quiet.label}
        </button>
        {failed && <div className="paper-mono" style={{ fontSize: 12, color: 'var(--warn)',
             textTransform: 'none', letterSpacing: 0 }}>
          kunne ikke gennemføres</div>}
      </div>
    </div>
  );
}

export default function PaperPanel({ dark = false }) {
  const { doc, error, now } = usePaperData(false, true);
  const [status, setStatus] = useState(null);
  const [hidden, setHidden] = useState(new Set());   // optimistisk skjulte ids
  const [failed, setFailed] = useState(new Set());   // ids med fejlet handling
  const [lettersFailed, setLettersFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => fetchPanelStatus()
      .then((s) => { if (alive) setStatus(s); })
      .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // /paper/panel følger solen (mørk efter solnedgang); /paper/panel/dark tvinger
  // mørk hele døgnet. Uden vejr-data falder isNight tilbage på 22–06.
  const night = dark || isNight(now, doc?.weather);
  const mode = night ? 'night' : undefined;

  if (!doc) return <div className="paper-root" data-mode={mode} />;

  const act = (item, action) => {
    setHidden((h) => new Set(h).add(item.id));
    setFailed((f) => { const n = new Set(f); n.delete(item.id); return n; });
    postTriageAction(item.id, action).catch(() => {
      setHidden((h) => { const n = new Set(h); n.delete(item.id); return n; });
      setFailed((f) => new Set(f).add(item.id));
    });
  };
  const actNewsletters = (ids) => {
    setHidden((h) => new Set([...h, ...ids]));
    setLettersFailed(false);
    archiveNewsletters().catch(() => {
      setHidden((h) => { const n = new Set(h); ids.forEach((i) => n.delete(i)); return n; });
      setLettersFailed(true);
    });
  };

  const { actionable, newsletters } = partitionInbox(doc.post);
  const inbox = actionable.filter((i) => !hidden.has(i.id));
  const letters = newsletters.filter((i) => !hidden.has(i.id));
  const withDue = (doc.tasks || []).filter((t) => t.due);
  withDue.sort((a, b) => a.due.localeCompare(b.due));
  const noDue = (doc.tasks || []).filter((t) => !t.due);
  const aulaRows = [...(doc.aula?.recent || []), ...(doc.aula?.info || [])].slice(0, 3);
  const dateLine = now.toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="paper-root" data-mode={mode} style={{ padding: '56px 64px', display: 'flex',
                                         flexDirection: 'column', fontSize: 16 }}>
      {/* — header med tung 2px-linje — */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                    paddingBottom: 26, borderBottom: '2px solid var(--ink)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 18 }}>
          <div style={{ fontSize: 26, fontWeight: 700 }}>LifeHub</div>
          <div className="paper-mono" style={{ fontSize: 14, letterSpacing: '.14em',
               color: 'var(--muted)' }}>HANDLINGSPANEL</div>
          {error && <div className="paper-mono" style={{ fontSize: 13, color: 'var(--faint)',
               textTransform: 'none', letterSpacing: 0 }}>
            opdateret {doc.generated_at?.slice(11, 16)} · offline</div>}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 22 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{dateLine}</div>
          <div className="paper-mono paper-clock" style={{ fontSize: 20, fontWeight: 500 }}>
            {fmtClock(now)}</div>
        </div>
      </div>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '460px 1fr 430px',
                    gap: 56, paddingTop: 36, minHeight: 0 }}>
        {/* — kolonne 1: opgaver — */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <SectionLabel right={`${(doc.tasks || []).length} · Vikunja`}>OPGAVER</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10 }}>
            {withDue.slice(0, 5).map((t) => {
              const due = dueLine(t.due, now);
              const urgent = due && (due.startsWith('i dag') || due === 'forfalden');
              return (
                <div key={t.id} style={{ display: 'flex', gap: 16, alignItems: 'baseline',
                     padding: '16px 0', borderBottom: '1px solid var(--hairline)' }}>
                  <div className="paper-dot" style={{ width: 18, height: 18,
                    border: `2px solid ${urgent ? 'var(--accent)' : 'var(--circle-idle)'}`,
                    transform: 'translateY(3px)' }} />
                  <div>
                    <div style={{ fontSize: 19, fontWeight: urgent ? 600 : 500 }}>
                      {stripEmoji(t.title)}</div>
                    <div className="paper-mono" style={{ fontSize: 13, marginTop: 3,
                         color: urgent ? 'var(--accent)' : 'var(--muted)',
                         textTransform: 'none', letterSpacing: 0 }}>{due}</div>
                  </div>
                </div>
              );
            })}
          </div>
          {noDue.length > 0 && (
            <div className="paper-mono" style={{ marginTop: 'auto', fontSize: 13,
                 color: 'var(--faint)', textTransform: 'none', letterSpacing: 0 }}>
              + {noDue.length} uden frist</div>
          )}
        </div>
        {/* — kolonne 2: indbakke-triage — */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0,
                      borderLeft: '1px solid var(--hairline-strong)',
                      borderRight: '1px solid var(--hairline-strong)', padding: '0 56px' }}>
          <SectionLabel right={doc.post ? `${doc.post.new_today} nye` : null}>
            INDBAKKE · TIL GENNEMSYN</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10, overflow: 'hidden' }}>
            {!doc.post && (
              <div style={{ fontSize: 17, color: 'var(--faint)', paddingTop: 18 }}>
                Ingen adgang til indbakken fra denne enhed.</div>
            )}
            {inbox.slice(0, 4).map((item) => (
              <InboxRow key={item.id} item={item} onAction={act} failed={failed.has(item.id)} />
            ))}
            {letters.length > 0 && (
              <div style={{ padding: '18px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--muted)' }}>
                    {letters.length} nyhedsbrev{letters.length === 1 ? '' : 'e'}</div>
                  <div className="paper-badge paper-badge--neutral" style={{ fontSize: 12 }}>
                    LAV PRIORITET</div>
                </div>
                <div style={{ marginTop: 12 }}>
                  <button onClick={() => actNewsletters(letters.map((l) => l.id))}
                          className="paper-pill"
                          style={{ fontSize: 15, fontWeight: 600, color: 'var(--muted)',
                                   padding: '6px 18px', background: 'none', cursor: 'pointer',
                                   fontFamily: 'inherit' }}>
                    Arkivér alle
                  </button>
                  {lettersFailed && <div className="paper-mono" style={{ fontSize: 12, color: 'var(--warn)', textTransform: 'none', letterSpacing: 0, marginTop: 8 }}>
  kunne ikke gennemføres
</div>}
                </div>
              </div>
            )}
          </div>
        </div>
        {/* — kolonne 3: Aula + DRIFT — */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <SectionLabel>AULA</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10 }}>
            {aulaRows.map((a, i) => {
              const badge = classBadge(a.title);
              return (
                <div key={i} style={{ padding: '16px 0', borderBottom: '1px solid var(--hairline)' }}>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                    <div className={`paper-badge${badge ? '' : ' paper-badge--neutral'}`}
                         style={{ fontSize: 13, flex: 'none' }}>{badge || 'AULA'}</div>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{stripEmoji(a.title)}</div>
                    {a.date && <div className="paper-mono" style={{ fontSize: 13,
                         color: 'var(--muted)', marginLeft: 'auto', textTransform: 'none',
                         letterSpacing: 0 }}>{a.date.slice(8, 10)}.{Number(a.date.slice(5, 7))}
                         {a.time ? ` · ${a.time.slice(0, 5)}` : ''}</div>}
                  </div>
                  {a.summary && <div style={{ fontSize: 16, color: 'var(--ink-2)', marginTop: 6,
                       lineHeight: 1.45 }}>{stripEmoji(a.summary)}</div>}
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 'auto' }}>
            <div className="paper-mono" style={{ fontSize: 14, color: 'var(--muted)',
                 paddingTop: 20, borderTop: '1px solid var(--hairline-strong)' }}>DRIFT</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14,
                          fontFamily: 'var(--font-mono)', fontSize: 14 }}>
              {status && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="paper-dot" style={{ width: 9, height: 9, background: 'var(--ok)' }} />
                  <div>brain (FastAPI)</div>
                  <div style={{ color: 'var(--faint)', marginLeft: 'auto' }}>{status.latency_ms} ms</div>
                </div>
              )}
              {(status?.services || []).map((s) => (
                <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10,
                     opacity: s.state === 'off' ? 0.45 : 1 }}>
                  <div className="paper-dot" style={{ width: 9, height: 9,
                    background: s.state === 'warn' ? 'var(--warn)' : 'var(--ok)' }} />
                  <div>{s.name}</div>
                  <div style={{ color: 'var(--faint)', marginLeft: 'auto' }}>{s.detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

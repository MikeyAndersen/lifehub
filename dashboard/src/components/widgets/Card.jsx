import { useEffect, useRef, useState } from 'react';

/* Fælles kort-skal: label venstre (evt. med chip), meta/handling højre.
   accent vælger cardets ene accentfarve (DEL 1); primary giver den statiske
   svage gradient-border; pulseKey udløser et blødt lysskifte når cardets
   data ændrer sig (DEL 2 — opacity-ease, aldrig et flash). */
export default function Card({ label, chip, meta, accent = 'system', primary, pulseKey, children }) {
  const [updated, setUpdated] = useState(false);
  const prev = useRef(pulseKey);

  useEffect(() => {
    if (pulseKey === undefined || prev.current === pulseKey) return;
    prev.current = pulseKey;
    setUpdated(true);
    const id = setTimeout(() => setUpdated(false), 1500);
    return () => clearTimeout(id);
  }, [pulseKey]);

  const cls = ['card', `card--${accent}`, primary && 'card--primary',
    updated && 'card--updated'].filter(Boolean).join(' ');
  return (
    <section className={cls}>
      <div className="card-head">
        <div className="card-label-group">
          <span className="card-label">{label}</span>
          {chip && <span className="chip">{chip}</span>}
        </div>
        {meta}
      </div>
      {children}
    </section>
  );
}

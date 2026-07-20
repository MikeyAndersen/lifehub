import { useEffect, useRef, useState } from 'react';

/* Lille dropdown i topbaren: alle read-only visnings-flader samlet ét sted.
   Space-temaet (rum-ur + orbit) og Warm Paper-temaet (tablet/wallpaper/panel).
   Lukker ved klik udenfor og på Escape; simpel <a>-navigation, ingen router. */
const AMBIENT_LINKS = [
  { href: '/ambient',           label: 'Ambient · rum-ur',       hint: 'Delt flade — Wallpaper Engine / køkkentablet' },
  { href: '/ambient/orbit',     label: 'Ambient · orbit',        hint: 'Observatorie-fuldskærm med systemstats' },
  { href: '/paper/tablet',      label: 'Warm Paper · tablet',    hint: 'Familie-dashboard, dag/nat' },
  { href: '/paper/wallpaper',   label: 'Warm Paper · wallpaper', hint: 'Ultrawide baggrundslag bag vinduer' },
  { href: '/paper/panel',       label: 'Warm Paper · panel',     hint: 'Handlingspanel (admin)' },
];

export default function AmbientMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="ambient-menu" ref={ref}>
      <button
        type="button"
        className="linkish"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        Ambient visning <span className="ambient-menu-caret" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="ambient-menu-pop" role="menu">
          {AMBIENT_LINKS.map((l) => (
            <a key={l.href} className="ambient-menu-item" role="menuitem" href={l.href}>
              <span className="ambient-menu-label">{l.label}</span>
              <span className="ambient-menu-hint">{l.hint}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

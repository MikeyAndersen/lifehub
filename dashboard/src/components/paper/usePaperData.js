/* Delt poll-hook for alle tre paper-flader. Samme kadence som space-temaets
   Dashboard.jsx: data hvert 120 s, klokke hvert 15 s. Ved fetch-fejl beholdes
   sidste gode dokument og error sættes — fladerne viser en stille mono-linje. */
import { useEffect, useState } from 'react';
import { fetchDashboard, fetchPanelFeed } from '../../lib/api.js';

/** ambient=true → /api/ambient (delt flade, ingen post/finans).
    panel=true   → /api/panel/feed (kan inkludere post via PANEL_INBOX_OPEN).
    ellers       → /api/dashboard (admin-gated post). */
export function usePaperData(ambient = false, panel = false) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    let alive = true;
    const load = () => (panel ? fetchPanelFeed() : fetchDashboard(ambient))
      .then((d) => { if (alive) { setDoc(d); setError(false); } })
      .catch(() => { if (alive) setError(true); });
    load();
    const dataId = setInterval(load, 120_000);
    const clockId = setInterval(() => setNow(new Date()), 15_000);
    return () => { alive = false; clearInterval(dataId); clearInterval(clockId); };
  }, [ambient, panel]);

  return { doc, error, now };
}

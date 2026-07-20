const BASE = import.meta.env.PUBLIC_API_BASE || '';

export async function fetchDashboard(ambient = false) {
  try {
    const res = await fetch(`${BASE}/api/${ambient ? 'ambient' : 'dashboard'}`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch (err) {
    // MOCK-FALLBACK: kun i dev, når brain-servicen ikke svarer.
    if (import.meta.env.DEV) {
      const { mockDocument } = await import('./mock.js');
      console.warn('[LifeHub] /api utilgængelig — viser MOCK-DATA (kun dev).', err);
      return mockDocument(ambient);
    }
    throw err;
  }
}

/** Warm Paper-panelets feed. Som /api/dashboard, men brain inkluderer
 *  post-triage når PANEL_INBOX_OPEN er slået til (betroet enhed). Finans
 *  kommer aldrig med. Falder tilbage til mock i dev som fetchDashboard. */
export async function fetchPanelFeed() {
  try {
    const res = await fetch(`${BASE}/api/panel/feed`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch (err) {
    if (import.meta.env.DEV) {
      const { mockDocument } = await import('./mock.js');
      console.warn('[LifeHub] /api/panel/feed utilgængelig — MOCK (kun dev).', err);
      return mockDocument(false);
    }
    throw err;
  }
}

/** Systemstats til /ambient/orbit (DEL 5). Server-cachet 45 s. */
export async function fetchAmbientStats() {
  try {
    const res = await fetch(`${BASE}/api/ambient/stats`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch (err) {
    if (import.meta.env.DEV) {
      const { mockAmbientStats } = await import('./mock.js');
      console.warn('[LifeHub] /api/ambient/stats utilgængelig — MOCK (kun dev).', err);
      return mockAmbientStats();
    }
    throw err;
  }
}

/** Event-puls til /ambient/orbit: nye sys_events efter afterId. */
export async function fetchAmbientEvents(afterId) {
  try {
    const q = afterId != null ? `?after_id=${afterId}` : '';
    const res = await fetch(`${BASE}/api/ambient/events${q}`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch (err) {
    if (import.meta.env.DEV) {
      const { mockAmbientEvents } = await import('./mock.js');
      return mockAmbientEvents(afterId);
    }
    throw err;
  }
}

/** Regenerér dagens brief manuelt (↻-knappen). Admin-gated i brain.
 *  Returnerer { ok, brief } så dashboardet kan opdatere med det samme. */
export async function regenerateBrief() {
  try {
    const res = await fetch(`${BASE}/api/brief/regenerate`, { method: 'POST' });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch (err) {
    if (import.meta.env.DEV) {
      const { mockDocument } = await import('./mock.js');
      return { ok: true, brief: { ...mockDocument().brief } };
    }
    throw err;
  }
}

/** Markér en opgave som færdig/åben i Vikunja via brain. Kaster ved fejl. */
export async function setTaskDone(id, done = true) {
  const res = await fetch(`${BASE}/api/tasks/${id}/done`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ done }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** DRIFT-footer til /paper/panel. Måler selv svartiden (brain-rækken). */
export async function fetchPanelStatus() {
  const t0 = performance.now();
  try {
    const res = await fetch(`${BASE}/api/panel/status`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const doc = await res.json();
    return { ...doc, latency_ms: Math.round(performance.now() - t0) };
  } catch (err) {
    if (import.meta.env.DEV) {
      const { mockPanelStatus } = await import('./mock.js');
      return mockPanelStatus();
    }
    throw err;
  }
}

/** Panel-pille: godkend/arkivér/udsæt et post-emne. Kaster ved fejl. */
export async function postTriageAction(id, action) {
  const res = await fetch(`${BASE}/api/post/${id}/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** Panel: arkivér alle pending nyhedsbreve. Kaster ved fejl. */
export async function archiveNewsletters() {
  const res = await fetch(`${BASE}/api/post/archive-newsletters`, { method: 'POST' });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

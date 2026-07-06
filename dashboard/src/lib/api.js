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

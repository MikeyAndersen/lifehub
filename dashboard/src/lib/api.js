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

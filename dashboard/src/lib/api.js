const BASE = import.meta.env.PUBLIC_API_BASE || '';

export async function fetchDashboard(ambient = false) {
  const res = await fetch(`${BASE}/api/${ambient ? 'ambient' : 'dashboard'}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export const fmtTime = (iso) =>
  iso?.includes('T') ? iso.slice(11, 16) : 'hele dagen';

export const fmtDay = (iso) => {
  const d = new Date(iso);
  const today = new Date();
  const tomorrow = new Date(Date.now() + 864e5);
  const same = (a, b) => a.toDateString() === b.toDateString();
  if (same(d, today)) return 'I dag';
  if (same(d, tomorrow)) return 'I morgen';
  return d.toLocaleDateString('da-DK', { weekday: 'short', day: 'numeric', month: 'short' });
};

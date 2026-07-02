import { useEffect, useState } from 'react';
import { fetchDashboard, fmtTime, fmtDay } from '../lib/api.js';

/* Read-only shared surface for Wallpaper Engine / kitchen tablet.
   Never renders finance — the /api/ambient endpoint never sends it. */
export default function Ambient() {
  const [data, setData] = useState(null);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const load = () => fetchDashboard(true).then(setData).catch(() => {});
    load();
    const dataId = setInterval(load, 60_000);
    const clockId = setInterval(() => setNow(new Date()), 1_000);
    return () => { clearInterval(dataId); clearInterval(clockId); };
  }, []);

  const hhmm = now.toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' });
  const dateStr = now.toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="ambient">
      <div>
        <div className="clock">{hhmm}</div>
        <div className="today">{dateStr}</div>
        {data?.brief?.text && <div className="brief">{data.brief.text}</div>}
        <div className="metaline">
          {data?.weather && <>{Math.round(data.weather.now_c)}° · regn {data.weather.rain_pct}% </>}
          {data?.elpris?.now_dkk_kwh != null && <> · el {data.elpris.now_dkk_kwh.toFixed(2)} kr/kWh</>}
        </div>
      </div>
      <div className="side">
        <h2>Næste</h2>
        {(data?.events || []).slice(0, 6).map((e, i) => (
          <div className="row" key={i}>
            <span className="t">{fmtDay(e.start)} {e.all_day ? '' : fmtTime(e.start)}</span>
            <span className="label">{e.title}</span>
          </div>
        ))}
        <h2>Opgaver</h2>
        {(data?.tasks || []).slice(0, 5).map((t) => (
          <div className="row" key={t.id}>
            <span className="t">{t.due ? fmtDay(t.due) : '—'}</span>
            <span className="label">{t.title}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { fetchDashboard, fmtTime, fmtDay } from '../lib/api.js';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = () => fetchDashboard().then(setData).catch((e) => setError(e.message));
    load();
    const id = setInterval(load, 120_000);
    return () => clearInterval(id);
  }, []);

  if (error) return <div className="err">Kunne ikke hente data ({error}). Kører brain-servicen?</div>;
  if (!data) return <div className="muted" style={{ padding: 24 }}>Henter…</div>;

  return (
    <>
      <Brief brief={data.brief} weather={data.weather} elpris={data.elpris} />
      <div className="grid">
        <Events events={data.events} />
        <Tasks tasks={data.tasks} />
        <Birthdays birthdays={data.birthdays} />
        {data.finance && <Finance finance={data.finance} />}
      </div>
    </>
  );
}

function Brief({ brief, weather, elpris }) {
  const today = new Date().toLocaleDateString('da-DK', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
  return (
    <div className="hero">
      <div className="date">
        {today}
        {weather && <> · {Math.round(weather.now_c)}° ({Math.round(weather.today_min)}–{Math.round(weather.today_max)}°, regn {weather.rain_pct}%)</>}
        {elpris?.now_dkk_kwh != null && <> · el {elpris.now_dkk_kwh.toFixed(2)} kr/kWh</>}
      </div>
      {brief?.text || <span className="muted">Dagens brief kommer kl. 06.30 — eller udløs den manuelt fra Telegram.</span>}
    </div>
  );
}

function Events({ events }) {
  return (
    <section className="card">
      <h2>Kalender · 7 dage</h2>
      {events.length === 0 && <p className="muted">Ingen aftaler — nyd friheden.</p>}
      {events.slice(0, 10).map((e, i) => (
        <div className="row" key={i}>
          <span className="t">{fmtDay(e.start)} {e.all_day ? '' : fmtTime(e.start)}</span>
          <span className="label">
            {e.title}
            {e.location && <div className="sub">{e.location}</div>}
          </span>
        </div>
      ))}
    </section>
  );
}

function Tasks({ tasks }) {
  return (
    <section className="card">
      <h2>Opgaver</h2>
      {tasks.length === 0 && <p className="muted">Alt er gjort. Imponerende.</p>}
      {tasks.slice(0, 10).map((t) => (
        <div className="row" key={t.id}>
          <span className="t">{t.due ? fmtDay(t.due) : '—'}</span>
          <span className="label">{t.title}</span>
        </div>
      ))}
    </section>
  );
}

function Birthdays({ birthdays }) {
  return (
    <section className="card">
      <h2>Fødselsdage · 30 dage</h2>
      {birthdays.length === 0 && <p className="muted">Ingen fødselsdage lige nu.</p>}
      {birthdays.map((b, i) => (
        <div className="row" key={i}>
          <span className="t">{fmtDay(b.date)}</span>
          <span className="label">{b.title}</span>
        </div>
      ))}
    </section>
  );
}

function Finance({ finance }) {
  return (
    <section className="card">
      <h2>Økonomi <span className="pill">privat</span></h2>
      {finance.status === 'not_configured' && (
        <p className="muted">Banktilslutning ikke sat op endnu (GoCardless) — viser noterede udgifter.</p>
      )}
      {finance.recent_expenses?.map((e, i) => (
        <div className="row" key={i}>
          <span className="t">{e.amount_dkk.toFixed(0)} kr</span>
          <span className="label">
            {e.title}
            <div className="sub">{e.noted_at?.slice(0, 10)}</div>
          </span>
        </div>
      ))}
    </section>
  );
}

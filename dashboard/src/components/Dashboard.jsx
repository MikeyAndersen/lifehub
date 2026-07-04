import { useEffect, useState } from 'react';
import { fetchDashboard } from '../lib/api.js';
import { fmtClock } from '../lib/format.js';
import Hero from './widgets/Hero.jsx';
import Kalender from './widgets/Kalender.jsx';
import Opgaver from './widgets/Opgaver.jsx';
import Foedselsdage from './widgets/Foedselsdage.jsx';
import Middag from './widgets/Middag.jsx';
import Afgange from './widgets/Afgange.jsx';
import Aula from './widgets/Aula.jsx';
import Oekonomi from './widgets/Oekonomi.jsx';

/* Interaktiv visning — telefon-først, flydende kort-flow.
   Kort for manglende datablokke skjules helt; flex-wrap-flowet
   sørger for at layoutet aldrig ser "hullet" ud. */
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(() => new Date());
  const [okoHidden, setOkoHidden] = useState(false);

  useEffect(() => {
    const load = () =>
      fetchDashboard()
        .then((d) => { setData(d); setError(null); })
        .catch((e) => setError(e.message));
    load();
    const dataId = setInterval(load, 120_000);
    const clockId = setInterval(() => setNow(new Date()), 15_000);
    return () => { clearInterval(dataId); clearInterval(clockId); };
  }, []);

  if (error && !data) {
    return <div className="err">Kunne ikke hente data ({error}). Kører brain-servicen?</div>;
  }
  if (!data) return <div className="muted" style={{ padding: 24 }}>Henter…</div>;

  return (
    <>
      <header className="topbar">
        <div className="topbar-brand">
          <h1>LifeHub</h1>
          <span className="topbar-dot" />
        </div>
        <div className="topbar-right">
          <span className="topbar-clock mono">{fmtClock(now)}</span>
          <a className="linkish" href="/ambient">Ambient visning</a>
        </div>
      </header>

      <Hero brief={data.brief} weather={data.weather} elpris={data.elpris} now={now} />

      <div className="cards">
        <Kalender events={data.events} />
        <Opgaver tasks={data.tasks} doneTasks={data.tasks_done} />
        <Foedselsdage birthdays={data.birthdays} />
        <Aula aula={data.aula} />
        <Middag madplan={data.madplan} />
        <Afgange transit={data.transit} now={now} />
        {data.finance && !okoHidden && (
          <Oekonomi finance={data.finance} onHide={() => setOkoHidden(true)} />
        )}
      </div>

      <footer className="footer">
        <span className="footer-text">LifeHub · selvhostet</span>
        {data.finance && okoHidden && (
          <button className="linkish" onClick={() => setOkoHidden(false)}>Vis økonomi</button>
        )}
      </footer>
    </>
  );
}

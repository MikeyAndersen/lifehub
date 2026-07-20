import { useEffect, useState } from 'react';
import { fetchDashboard, regenerateBrief } from '../lib/api.js';
import { fmtClock } from '../lib/format.js';
import { startDaycycle } from '../lib/daycycle.js';
import Backdrop from './Backdrop.jsx';
import AmbientMenu from './AmbientMenu.jsx';
import Hero from './widgets/Hero.jsx';
import Kalender from './widgets/Kalender.jsx';
import Opgaver from './widgets/Opgaver.jsx';
import Foedselsdage from './widgets/Foedselsdage.jsx';
import Ugeplan from './widgets/Ugeplan.jsx';
import Beholdning from './widgets/Beholdning.jsx';
import Afgange from './widgets/Afgange.jsx';
import Aula from './widgets/Aula.jsx';
import Post from './widgets/Post.jsx';
import Oekonomi from './widgets/Oekonomi.jsx';

/* Interaktiv visning — telefon-først, flydende kort-flow.
   Kort for manglende datablokke skjules helt; flex-wrap-flowet
   sørger for at layoutet aldrig ser "hullet" ud. */
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(() => new Date());
  const [okoHidden, setOkoHidden] = useState(false);
  const [briefBusy, setBriefBusy] = useState(false);
  const [briefErr, setBriefErr] = useState(null);

  const regenerate = async () => {
    if (briefBusy) return;
    setBriefBusy(true);
    setBriefErr(null);
    try {
      const r = await regenerateBrief();
      setData((d) => ({ ...d, brief: r.brief })); // opdatér straks, vent ikke på poll
    } catch {
      setBriefErr('Kunne ikke generere brief lige nu — LLM svarer måske ikke.');
    } finally {
      setBriefBusy(false);
    }
  };

  useEffect(() => {
    const load = () =>
      fetchDashboard()
        .then((d) => { setData(d); setError(null); })
        .catch((e) => setError(e.message));
    load();
    const dataId = setInterval(load, 120_000);
    const clockId = setInterval(() => setNow(new Date()), 15_000);
    const stopDaycycle = startDaycycle();
    return () => { clearInterval(dataId); clearInterval(clockId); stopDaycycle(); };
  }, []);

  if (error && !data) {
    return <div className="err">Kunne ikke hente data ({error}). Kører brain-servicen?</div>;
  }
  if (!data) return <div className="muted" style={{ padding: 24 }}>Henter…</div>;

  return (
    <>
      <Backdrop />
      <header className="topbar">
        <div className="topbar-brand">
          <h1>LifeHub</h1>
          <span className="topbar-dot" />
        </div>
        <div className="topbar-right">
          <span className="topbar-clock mono">{fmtClock(now)}</span>
          <AmbientMenu />
        </div>
      </header>

      <Hero
        brief={data.brief}
        weather={data.weather}
        elpris={data.elpris}
        now={now}
        canRegenerate={data.is_admin}
        briefBusy={briefBusy}
        briefError={briefErr}
        onRegenerate={regenerate}
      />

      <div className="cards">
        <Kalender events={data.events} />
        <Foedselsdage birthdays={data.birthdays} />
        <Opgaver tasks={data.tasks} doneTasks={data.tasks_done} />
        <Aula aula={data.aula} />
        <Post post={data.post} />
        <Ugeplan madplan={data.madplan} />
        <Beholdning beholdning={data.beholdning} />
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

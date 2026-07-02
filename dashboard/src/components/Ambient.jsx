import { useEffect, useMemo, useState } from 'react';
import { fetchDashboard } from '../lib/api.js';
import OrbitClock from './ambient/OrbitClock.jsx';
import AmbientColumn from './ambient/AmbientColumn.jsx';
import Wings from './ambient/Wings.jsx';

/* Ambient visning — read-only delt flade for Wallpaper Engine / køkkentablet.
   Viser ALDRIG økonomi; /api/ambient sender det aldrig, og mock'en heller ikke.

   To tilstande, valgt automatisk efter viewportens sideforhold:
   - ultrawide (> 21:9): 5120×1440-scene med solsystem-"vinger" om midterzonen
   - tablet (ellers):    1920×1200-scene, kun midterzonen, helt statisk       */

const ULTRAWIDE_ASPECT = 21 / 9;

function useViewport() {
  const [size, setSize] = useState(null); // null indtil hydreret (SSR har intet window)
  useEffect(() => {
    const measure = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);
  return size;
}

export default function Ambient() {
  const [data, setData] = useState(null);
  const [now, setNow] = useState(() => new Date());
  const size = useViewport();

  useEffect(() => {
    const load = () => fetchDashboard(true).then(setData).catch(() => {});
    load();
    const dataId = setInterval(load, 60_000);
    const clockId = setInterval(() => setNow(new Date()), 1_000);
    return () => { clearInterval(dataId); clearInterval(clockId); };
  }, []);

  // Dagens tidsatte aftaler er planeter på urskiven.
  const todayKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const todayEvents = useMemo(
    () => (data?.events || []).filter((e) => !e.all_day && e.start.slice(0, 10) === todayKey),
    [data, todayKey],
  );

  if (!size) return null;

  const ultrawide = size.w / size.h > ULTRAWIDE_ASPECT;
  const stageW = ultrawide ? 5120 : 1920;
  const stageH = ultrawide ? 1440 : 1200;
  const fitScale = Math.min(size.w / stageW, size.h / stageH);

  return (
    <div className="amb-viewport">
      <div
        className="amb-stage"
        style={{ width: stageW, height: stageH, transform: `scale(${fitScale})` }}
      >
        {ultrawide && <Wings />}
        <div className="amb-center" style={{ transform: ultrawide ? 'none' : 'scale(0.833)' }}>
          <OrbitClock now={now} events={todayEvents} />
          <AmbientColumn data={data} now={now} />
        </div>
      </div>
    </div>
  );
}

import { fmtTime, fmtDue, fmtDkk, isOverdue, weatherLabel, elprisLevel, p2 } from '../../lib/format.js';

const WDS = ['søn', 'man', 'tir', 'ons', 'tor', 'fre', 'lør'];
const SEP = '  ·  ';

/* Funktionel kolonne — brief som hero-tekst, afgangstavle-kalender,
   top-3 opgaver og én meta-linje. Manglende datablokke udelades stille. */
export default function AmbientColumn({ data, now }) {
  const todayKey = `${now.getFullYear()}-${p2(now.getMonth() + 1)}-${p2(now.getDate())}`;
  const events = (data?.events || []).slice(0, 6);
  const tasks = (data?.tasks || []).slice(0, 3);

  const meta = [];
  if (data?.weather) {
    meta.push(`${Math.round(data.weather.now_c)}° ${weatherLabel(data.weather.code)}`);
  }
  if (data?.elpris?.now_dkk_kwh != null) {
    const level = elprisLevel(data.elpris);
    meta.push(`elpris ${fmtDkk(data.elpris.now_dkk_kwh)} kr/kWh${level ? ` · ${level}` : ''}`);
  }
  const deps = (data?.transit?.departures || [])
    .filter((iso) => new Date(iso) >= now)
    .slice(0, 2)
    .map(fmtTime);
  if (data?.transit?.station && deps.length) {
    meta.push(`${data.transit.station} ${deps.join(' · ')}`);
  }
  if (data?.aula?.new_today > 0) {
    meta.push(`Aula: ${data.aula.new_today} ny${data.aula.new_today === 1 ? '' : 'e'} i dag`);
  }

  return (
    <div className="amb-col">
      {data?.brief?.text && <div className="amb-brief">{data.brief.text}</div>}

      {events.length > 0 && (
        <div>
          <div className="amb-section-label">Kalender</div>
          <div>
            {events.map((e, i) => {
              const today = e.start.slice(0, 10) === todayKey;
              const prefix = today ? '' : WDS[new Date(e.start).getDay()] + ' ';
              return (
                <div className="amb-ev-row" key={i}>
                  <span className={`amb-ev-time${today ? ' today' : ''}`}>
                    {prefix && <span className="amb-ev-prefix">{prefix}</span>}
                    {e.all_day ? 'hele dagen' : fmtTime(e.start)}
                  </span>
                  <span className="amb-ev-title">{e.title}</span>
                  <span className="amb-ev-loc">{e.location}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tasks.length > 0 && (
        <div>
          <div className="amb-section-label">Opgaver</div>
          <div>
            {tasks.map((t) => {
              const overdue = isOverdue(t.due);
              return (
                <div className="amb-task-row" key={t.id}>
                  <span className={`amb-task-dot${overdue ? ' overdue' : ''}`} />
                  <span className="amb-task-title">{t.title}</span>
                  <span className={`amb-task-due${overdue ? ' overdue' : ''}`}>
                    {t.due ? fmtDue(t.due) : ''}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {meta.length > 0 && <div className="amb-metaline">{meta.join(SEP)}</div>}
    </div>
  );
}

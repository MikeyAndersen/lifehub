import { fmtDateLine, fmtDkk, weatherLabel, elprisLevel } from '../../lib/format.js';
import useCountUp from '../../lib/useCountUp.js';

const SEP = ' · ';

/* Dagens brief — hero-kortet øverst. */
export default function Hero({ brief, weather, elpris, now }) {
  const level = elprisLevel(elpris);
  const temp = useCountUp(weather ? Math.round(weather.now_c) : null);
  const pris = useCountUp(elpris?.now_dkk_kwh ?? null, { decimals: 2 });
  return (
    <div className="hero">
      <div className="hero-meta">
        <span className="sig">{fmtDateLine(now)}</span>
        {weather && (
          <>
            <span className="sep">{SEP}</span>
            <span className="val">{temp}° {weatherLabel(weather.code)}</span>
          </>
        )}
        {elpris?.now_dkk_kwh != null && (
          <>
            <span className="sep">{SEP}</span>
            <span className="val">elpris {fmtDkk(pris)} kr/kWh{level ? ` · ${level}` : ''}</span>
          </>
        )}
      </div>
      <div className="hero-text">
        {brief?.text || (
          <span className="muted">Dagens brief kommer kl. 06.30 — eller udløs den manuelt fra Telegram.</span>
        )}
      </div>
    </div>
  );
}

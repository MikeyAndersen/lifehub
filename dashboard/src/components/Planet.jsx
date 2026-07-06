import { daylight } from '../lib/daycycle.js';

/* Hovedplanet (DEL 3): stor stiliseret planet øverst på hovedskærmen.
   Ren CSS/inline-styles med layered radial-gradients. Afspejler roligt
   det aktuelle vejr fra det eksisterende weather-feed (WMO-koder):
   klart = blød atmosfære · skyet = blurede ellipser der driver umærkeligt
   · regn = få svage streaks + køligere tone · blæst = lidt hurtigere
   sky-drift · nat = mørkere planet med svage bylys. Terminator-linjen
   (lys/skygge) vandrer langsomt med døgnet. Ingen dramatik: alle
   opaciteter er hints, al drift er 45–90s. Reduced motion fryser alt
   via den globale animation-regel. */

const CLOUDS = [
  { top: '22%', left: '-18%', w: 68, h: 16, dur: 78, delay: 0 },
  { top: '46%', left: '-30%', w: 84, h: 18, dur: 92, delay: -31 },
  { top: '66%', left: '-12%', w: 55, h: 13, dur: 64, delay: -12 },
];

const RAIN = [
  { left: '24%', delay: 0 }, { left: '41%', delay: -1.6 }, { left: '57%', delay: -0.7 },
  { left: '70%', delay: -2.3 }, { left: '84%', delay: -1.1 },
];

const CITY_LIGHTS = [
  { top: '58%', left: '30%' }, { top: '64%', left: '44%' }, { top: '55%', left: '52%' },
  { top: '70%', left: '38%' }, { top: '62%', left: '61%' }, { top: '73%', left: '55%' },
];

export default function Planet({ weather, now }) {
  const hour = now.getHours() + now.getMinutes() / 60;
  const day = daylight(hour);
  const night = day < 0.18;
  const code = weather?.code ?? 0;
  const cloudy = code === 2 || code === 3 || (code >= 45 && code <= 48);
  const rainy = (code >= 51 && code <= 67) || (code >= 80 && code <= 82) || code >= 95;
  const windy = (weather?.wind_ms ?? 0) >= 8;

  // Terminator: skyggesiden roterer langsomt med døgnet; mængden af skygge
  // følger dagslyset. Ved midnat vender skyggen "mod" beskueren.
  const angle = ((hour / 24) * 360 + 180) % 360;
  const shadeOpacity = 0.25 + (1 - day) * 0.5;

  return (
    <div className="planet-wrap" aria-hidden="true">
      <div className={`planet${night ? ' planet--night' : ''}${rainy ? ' planet--rain' : ''}`}>
        <div className="planet-surface" />
        {(cloudy || rainy) && (
          <div className="planet-clouds">
            {CLOUDS.map((c, i) => (
              <span
                key={i}
                className="planet-cloud"
                style={{
                  top: c.top, left: c.left, width: `${c.w}%`, height: `${c.h}%`,
                  animationDuration: `${windy ? Math.round(c.dur * 0.6) : c.dur}s`,
                  animationDelay: `${c.delay}s`,
                }}
              />
            ))}
          </div>
        )}
        {rainy && (
          <div className="planet-rain">
            {RAIN.map((r, i) => (
              <span key={i} className="planet-drop" style={{ left: r.left, animationDelay: `${r.delay}s` }} />
            ))}
          </div>
        )}
        {night && (
          <div className="planet-city">
            {CITY_LIGHTS.map((p, i) => (
              <span key={i} className="planet-light" style={{ top: p.top, left: p.left }} />
            ))}
          </div>
        )}
        <div
          className="planet-terminator"
          style={{ transform: `rotate(${angle.toFixed(1)}deg)`, opacity: shadeOpacity }}
        />
        <div className="planet-atmo" />
      </div>
    </div>
  );
}

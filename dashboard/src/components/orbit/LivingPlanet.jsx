import { sunState } from '../../lib/daycycle.js';

/* Den levende planet (orbit-centrum). Afløser den tidligere neutrale orb:
   en blød, dæmpet klode der følger DØGNET og VEJRET fra ambient-feedet,
   med et diskret narrativt liv — et enkelt hus og en bil der en gang
   imellem kører en tur ad en vej hele vejen rundt om kloden.

   Alt er roligt og subtilt (space-observatorium, ikke tegnefilm): solen
   står op ved den rigtige solopgang og går ned ved solnedgang, skyer
   driver umærkeligt (lidt hurtigere i blæst), regn er få svage streaks,
   natten dæmper kloden og tænder nogle få bylys. Bilen er væk det meste
   af tiden og glider forbi ~hvert minut. prefers-reduced-motion fryser
   bevægelsen via den globale CSS-regel. */

const S = 200, C = S / 2, SUN_R = 116;

function weatherFlags(weather) {
  const code = weather?.code ?? 0;
  return {
    cloudy: code === 2 || code === 3 || (code >= 45 && code <= 48),
    rainy: (code >= 51 && code <= 67) || (code >= 80 && code <= 82) || code >= 95,
    windy: (weather?.wind_ms ?? 0) >= 8,
  };
}

const CLOUDS = [
  { top: 30, w: 66, h: 15, dur: 82, delay: 0 },
  { top: 92, w: 82, h: 17, dur: 96, delay: -37 },
  { top: 132, w: 52, h: 12, dur: 68, delay: -15 },
];
const RAIN = [46, 74, 104, 128, 156];
const CITY = [[118, 120], [138, 132], [150, 112], [126, 146], [162, 128]];

export default function LivingPlanet({ weather, now, flashKey }) {
  const sun = sunState(now, weather?.sunrise, weather?.sunset);
  const { cloudy, rainy, windy } = weatherFlags(weather);

  // Klodens lysstyrke følger solhøjden; natten dæmper roligt.
  const brightness = sun.up ? 0.62 + 0.5 * sun.altitude : 0.5;
  // Solens position: op i øst (venstre), over toppen, ned i vest (højre).
  const rad = Math.PI * (1 - sun.frac);
  const sunX = C + SUN_R * Math.cos(rad);
  const sunY = C - SUN_R * Math.sin(rad);
  // Lyssiden peger mod solen; om natten ingen dagslys-gradient.
  const lightX = sun.up ? 50 + 42 * Math.cos(rad) : 50;
  const lightY = sun.up ? 50 - 42 * Math.sin(rad) : 34;

  return (
    <div className="lp" aria-hidden="true">
      <div className="lp-halo" />
      {sun.up
        ? <div className="lp-sun" style={{ left: sunX, top: sunY, opacity: 0.35 + 0.5 * sun.altitude }} />
        : <div className="lp-moon" />}
      <div className="lp-globe" style={{ filter: `brightness(${brightness.toFixed(2)})` }}>
        <div className="lp-surface" />
        <div
          className="lp-daylight"
          style={{
            opacity: sun.up ? 0.22 + 0.55 * sun.altitude : 0,
            background: `radial-gradient(circle at ${lightX}% ${lightY}%, rgb(var(--tod-tint) / 0.9), transparent 58%)`,
          }}
        />
        {sun.night && (
          <div className="lp-city">
            {CITY.map(([x, y], i) => (
              <span key={i} className="lp-light" style={{ left: x, top: y }} />
            ))}
          </div>
        )}
        {(cloudy || rainy) && (
          <div className="lp-clouds">
            {CLOUDS.map((c, i) => (
              <span
                key={i}
                className="lp-cloud"
                style={{
                  top: c.top, width: c.w, height: c.h,
                  animationDuration: `${windy ? Math.round(c.dur * 0.6) : c.dur}s`,
                  animationDelay: `${c.delay}s`,
                }}
              />
            ))}
          </div>
        )}
        {rainy && (
          <div className="lp-rain">
            {RAIN.map((x, i) => (
              <span key={i} className="lp-drop" style={{ left: x, animationDelay: `${-i * 0.6}s` }} />
            ))}
          </div>
        )}
        {/* Skyggesiden modsat solen — vandrer umærkeligt hen over døgnet. */}
        <div
          className="lp-terminator"
          style={{ opacity: 0.28 + (1 - sun.altitude) * 0.32, transform: `rotate(${(sun.frac * 180).toFixed(1)}deg)` }}
        />
        <div className="lp-house" />
        <div className="lp-atmo" />
      </div>

      {/* Vejen rundt om kloden + bilen der kører en tur en gang imellem. */}
      <div className="lp-road-plane">
        <div className="lp-road" />
        <div className="lp-car-track"><span className="lp-car" /></div>
      </div>

      {flashKey > 0 && <div className="lp-flash" key={flashKey} />}
    </div>
  );
}

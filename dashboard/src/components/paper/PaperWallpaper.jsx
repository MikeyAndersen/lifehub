/* Warm Paper ultrawide-wallpaper (mockup 1f, 5120×1440). Center ≥2900px er
   TOMT — vinduer bor der. Intet handlingsbart, intet der haster.
   Drift-hastighed: ?drift=<sekunder> (produktionsdefault 320s; demo ~70s). */
import { usePaperData } from './usePaperData.js';
import { isNight } from './paperNight.js';
import { nextDays, stripEmoji, pickHighlights } from './paperLogic.js';
import { isoWeek, weatherLabel } from '../../lib/format.js';
import WeatherIcon from './WeatherIcon.jsx';

// Lyspletterne bærer temaet: lyse cremeglow på papir; på mørk baggrund er de
// dæmpede varme glow (≤.12 opacity) så kontrasten i teksten forbliver stærk.
const PATCHES = [
  { left: -400, top: 90, w: 1500, h: 420, color: 'rgba(255,253,246,1)', colorDark: 'rgba(232,224,211,.06)', blur: 40, anim: 'lh-drift-a', mult: 1, delay: '0s' },
  { left: -600, top: 640, w: 1100, h: 340, color: 'rgba(185,92,56,.14)', colorDark: 'rgba(201,138,103,.12)', blur: 50, anim: 'lh-drift-a', mult: 1.3, delay: '-40s' },
  { left: 0, top: 340, w: 1300, h: 380, color: 'rgba(255,253,246,.95)', colorDark: 'rgba(232,224,211,.05)', blur: 45, anim: 'lh-drift-b', mult: 1.15, delay: '-25s' },
  { left: -300, top: 1080, w: 900, h: 300, color: 'rgba(222,207,178,.8)', colorDark: 'rgba(201,138,103,.07)', blur: 38, anim: 'lh-drift-a', mult: 1.5, delay: '-70s' },
];

export default function PaperWallpaper({ dark = false }) {
  const { doc, now } = usePaperData(true);
  // /paper/wallpaper følger solen (mørk efter solnedgang); /paper/wallpaper/dark
  // tvinger mørk hele døgnet. Uden vejr-data falder isNight tilbage på 22–06.
  const night = dark || isNight(now, doc?.weather);
  const bg = night ? '#211d19' : '#f1ede4';
  const mode = night ? 'night' : undefined;
  // Astro pre-renders client:load components on the server (output: 'static'),
  // where `window` doesn't exist — guard so the build doesn't crash. In the
  // browser this still reads the live query string on every render.
  const search = typeof window !== 'undefined' ? window.location.search : '';
  const drift = Number(new URLSearchParams(search).get('drift')) || 320;
  if (!doc) return <div className="paper-root" data-mode={mode} style={{ '--paper-bg': bg }} />;

  const w = doc.weather;
  const days = nextDays(doc.events, now, 3);
  const note = pickHighlights(doc, now)[0];
  const weekday = now.toLocaleDateString('da-DK', { weekday: 'long' }).toUpperCase();
  const month = now.toLocaleDateString('da-DK', { month: 'long' });

  return (
    <div className="paper-root" data-mode={mode} style={{ '--paper-bg': bg, position: 'relative' }}>
      {/* — drivende lyspletter (hele bredden; produktion ≥300 s pr. tur) — */}
      {PATCHES.map((p, i) => (
        <div key={i} className="paper-drift" style={{ position: 'absolute',
          left: p.left, top: p.top, width: p.w, height: p.h,
          background: `radial-gradient(closest-side, ${night ? p.colorDark : p.color}, transparent)`,
          filter: `blur(${p.blur}px)`,
          animation: `${p.anim} ${Math.round(drift * p.mult)}s linear infinite`,
          animationDelay: p.delay }} />
      ))}
      {/* — venstre vinge — */}
      <div className="paper-sway" style={{ position: 'absolute', left: 150, top: 130,
           bottom: 130, width: 900, display: 'flex', flexDirection: 'column', zIndex: 1,
           animation: 'lh-sway var(--sway-a) ease-in-out infinite' }}>
        <div className="paper-mono" style={{ fontSize: 30, letterSpacing: '.18em',
             color: 'var(--muted)' }}>{weekday} · UGE {isoWeek(now)}</div>
        <div className="paper-clock" style={{ fontSize: 560, fontWeight: 600,
             letterSpacing: '-0.05em', lineHeight: 0.9, marginTop: 20 }}>{now.getDate()}</div>
        <div style={{ fontSize: 76, fontWeight: 600, letterSpacing: '-0.01em', marginTop: 24 }}>
          {month} <span style={{ color: 'var(--muted)', fontWeight: 400 }}>{now.getFullYear()}</span>
        </div>
        {w && (
          <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 44 }}>
            <WeatherIcon code={w.code} size={128} strokeWidth={1.4}
                         style={{ color: 'var(--ink-2)' }} />
            <div style={{ fontSize: 150, fontWeight: 500, letterSpacing: '-0.03em' }}>
              {Math.round(w.now_c)}°</div>
            <div>
              <div style={{ fontSize: 44, color: 'var(--ink-2)' }}>
                {weatherLabel(w.code).charAt(0).toUpperCase() + weatherLabel(w.code).slice(1)}
              </div>
              <div className="paper-mono" style={{ fontSize: 30, color: 'var(--muted)', marginTop: 10 }}>
                ↑ {w.sunrise?.slice(11, 16)}&nbsp;&nbsp;↓ {w.sunset?.slice(11, 16)}
              </div>
            </div>
          </div>
        )}
      </div>
      {/* — højre vinge — */}
      <div className="paper-sway" style={{ position: 'absolute', right: 150, top: 130,
           bottom: 130, width: 820, display: 'flex', flexDirection: 'column',
           alignItems: 'flex-end', textAlign: 'right', zIndex: 1,
           animation: 'lh-sway var(--sway-b) ease-in-out infinite', animationDelay: '-55s' }}>
        <div className="paper-mono" style={{ fontSize: 30, letterSpacing: '.18em',
             color: 'var(--muted)' }}>DE NÆSTE DAGE</div>
        <div style={{ display: 'flex', flexDirection: 'column', marginTop: 34, width: '100%' }}>
          {days.map((d, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                 alignItems: 'baseline', padding: '30px 0',
                 borderBottom: i < days.length - 1 ? '1px solid var(--hairline-strong)' : 'none' }}>
              <div style={{ fontSize: 44, fontWeight: 600 }}>
                {d.weekday}
                {d.badges.map((b, j) => (
                  <span key={j} className="paper-badge" style={{ fontSize: 28,
                        fontWeight: 400, marginLeft: 14 }}>{b}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
        {note && (
          <div style={{ marginTop: 'auto', fontSize: 44, color: 'var(--ink-2)', lineHeight: 1.4 }}>
            I dag: {note.text} <span className="paper-breathe" style={{ color: 'var(--accent)',
              display: 'inline-block', animation: 'lh-breathe 7s ease-in-out infinite' }}>●</span>
          </div>
        )}
      </div>
      <div className="paper-mono" style={{ position: 'absolute', left: '50%', bottom: 70,
           transform: 'translateX(-50%)', fontSize: 26, letterSpacing: '.3em',
           color: 'var(--hairline-strong)' }}>· · ·</div>
    </div>
  );
}

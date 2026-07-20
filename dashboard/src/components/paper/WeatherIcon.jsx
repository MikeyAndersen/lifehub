/* Minimalistiske vejr-ikoner til Warm Paper-fladerne. Ét tyndt streg-udtryk
   (currentColor, runde hjørner) — samme rolige, skandinaviske stil som resten
   af temaet: ingen fyld, ingen farver ud over blækket. WMO-koder mappes med
   samme tærskler som format.js' weatherLabel, så ikon og tekst altid følges ad. */

/** WMO-vejrkode → ikon-nøgle (samme grupper som weatherLabel). */
export function weatherIconKind(code) {
  if (code === 0) return 'clear';
  if (code <= 2) return 'partly';
  if (code === 3) return 'overcast';
  if (code <= 48) return 'fog';
  if (code <= 57) return 'drizzle';
  if (code <= 67) return 'rain';
  if (code <= 77) return 'snow';
  if (code <= 82) return 'rain';
  if (code <= 86) return 'snow';
  return 'thunder';
}

// Genbrugt sky-silhuet (feather-agtig), tegnet så regn/sne/torden hænger under.
const CLOUD = 'M17.5 18.5h-10a4 4 0 0 1 -0.4 -7.98 A5.5 5.5 0 0 1 17.6 9.7 a3.6 3.6 0 0 1 -0.1 8.8 z';

function Shape({ kind }) {
  switch (kind) {
    case 'clear':
      return (
        <>
          <circle cx="12" cy="12" r="4.4" />
          <path d="M12 3v2.2M12 18.8v2.2M3 12h2.2M18.8 12h2.2M5.6 5.6l1.5 1.5M16.9 16.9l1.5 1.5M18.4 5.6l-1.5 1.5M7.1 16.9l-1.5 1.5" />
        </>
      );
    case 'partly':
      return (
        <>
          <circle cx="8.5" cy="8" r="3.1" />
          <path d="M8.5 1.9v1.5M2.4 8h1.5M4.3 3.8l1 1M12.7 3.8l-1 1M2.4 12.2l1-1" />
          <path d="M18 19h-8a3.4 3.4 0 0 1 -0.35 -6.78 A4.7 4.7 0 0 1 18.1 11 a3.1 3.1 0 0 1 -0.1 8 z" />
        </>
      );
    case 'overcast':
      return (
        <>
          <path d={CLOUD} />
          <path d="M6.5 8.2A4.6 4.6 0 0 1 13.9 6" opacity="0.55" />
        </>
      );
    case 'fog':
      return (
        <>
          <path d={CLOUD} />
          <path d="M4.5 21h9M8.5 18.2h11" opacity="0.7" />
        </>
      );
    case 'drizzle':
      return (
        <>
          <path d={CLOUD} />
          <path d="M8.5 20v1.6M12 20v1.6M15.5 20v1.6" />
        </>
      );
    case 'rain':
      return (
        <>
          <path d={CLOUD} />
          <path d="M8 20l-1 2.4M12 20l-1 2.4M16 20l-1 2.4" />
        </>
      );
    case 'snow':
      return (
        <>
          <path d={CLOUD} />
          <path d="M8.5 21h.01M12 22h.01M15.5 21h.01M12 19.6h.01" />
        </>
      );
    case 'thunder':
      return (
        <>
          <path d={CLOUD} />
          <path d="M13 19.5l-3 4h3l-2 3" />
        </>
      );
    default:
      return null;
  }
}

/** Inline vejr-ikon. Arver farve fra teksten; `size` i px. */
export default function WeatherIcon({ code, size = 40, strokeWidth = 1.6, style }) {
  const kind = weatherIconKind(code);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flex: 'none', ...style }}
    >
      <Shape kind={kind} />
    </svg>
  );
}

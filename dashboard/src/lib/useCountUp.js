import { useEffect, useRef, useState } from 'react';

/* Blød optælling af en talværdi (DEL 2): ease-out cubic over 800ms via
   requestAnimationFrame. prefers-reduced-motion → værdien hopper direkte.
   Ikke-numeriske værdier (null/undefined) passerer uændret igennem. */
export default function useCountUp(value, { duration = 800, decimals = 0 } = {}) {
  const [shown, setShown] = useState(value);
  const fromRef = useRef(value);

  useEffect(() => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      fromRef.current = value;
      setShown(value);
      return;
    }
    const from = typeof fromRef.current === 'number' ? fromRef.current : value;
    fromRef.current = value;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced || from === value) {
      setShown(value);
      return;
    }
    let raf;
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / duration);
      const eased = 1 - (1 - k) ** 3;
      setShown(Number((from + (value - from) * eased).toFixed(decimals)));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, decimals]);

  // null→tal-overgang: effekten halter én tick efter — vis målværdien direkte.
  return typeof value === 'number' && typeof shown !== 'number' ? value : shown;
}

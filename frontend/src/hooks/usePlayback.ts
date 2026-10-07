import { useEffect, useRef, useState } from "react";

export function usePlayback(horizon: number) {
  const [t, setTState] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const tRef = useRef(0);

  const setT = (value: number) => {
    tRef.current = value;
    setTState(value);
  };

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const next = Math.min(horizon, tRef.current + ((now - last) / 250) * speed);
      last = now;
      tRef.current = next;
      setTState(next);
      if (next >= horizon) {
        setPlaying(false);
        return;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, horizon]);

  return { t, setT, playing, setPlaying, speed, setSpeed };
}

"use client";

import { useEffect, useState } from "react";

export function Duration({ startedAt }: { startedAt: string | null | undefined }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!startedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  if (!startedAt) {
    return <span className="font-mono tabular-nums">—</span>;
  }

  const start = new Date(startedAt).getTime();
  const sec = Math.max(0, Math.floor((now - start) / 1000));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  const elapsed = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

  return <span className="font-mono tabular-nums">{elapsed}</span>;
}

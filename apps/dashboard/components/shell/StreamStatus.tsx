"use client";

import type { CycleStreamSnapshot } from "@/src/api/sse/use-cycle-event-stream";

function formatTime(d: Date | null): string {
  if (!d) return "—";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export type StreamStatusProps = {
  stream: CycleStreamSnapshot;
};

export function StreamStatus({ stream }: StreamStatusProps) {

  const live = stream.state === "live";
  const label = live
    ? `Live · refreshed ${formatTime(stream.lastRefreshAt ?? stream.lastEventAt)}`
    : stream.state === "connecting"
      ? "Connecting…"
      : `Disconnected · last refresh ${formatTime(stream.lastRefreshAt)}`;

  return (
    <span
      className={`ol-stream inline-flex items-center gap-1.5 text-xs font-mono text-[var(--text-secondary)] ${live ? "" : "is-off"}`}
      role="status"
    >
      <span className="ol-stream-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

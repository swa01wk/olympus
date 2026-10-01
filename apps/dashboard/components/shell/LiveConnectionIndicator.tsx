"use client";

import { useEventStreamStatus } from "@/lib/events/use-event-stream";

export function LiveConnectionIndicator() {
  const status = useEventStreamStatus();
  const tone =
    status === "LIVE"
      ? "text-emerald-400"
      : status === "RECONNECTING" || status === "CONNECTING"
        ? "text-amber-400"
        : "text-[var(--muted)]";
  return (
    <span className={`text-xs ${tone}`} aria-live="polite">
      SSE: {status}
    </span>
  );
}

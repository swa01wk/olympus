"use client";

import { ExceptionState } from "@/components/truth/ExceptionState";

export function StreamDisconnectedNotice({
  lastRefreshAt,
  onRefetch,
}: {
  lastRefreshAt: Date | null;
  onRefetch?: () => void;
}) {
  const when = lastRefreshAt
    ? lastRefreshAt.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "never";

  return (
    <ExceptionState
      status="stale"
      statusLabel="Event stream disconnected"
      reason={`Last authoritative refresh at ${when}. Live updates are paused.`}
      consequence="Do not assume lifecycle completion from stale UI — refetch before issuing commands."
      action={onRefetch ? { label: "Refetch now", onClick: onRefetch } : undefined}
    />
  );
}

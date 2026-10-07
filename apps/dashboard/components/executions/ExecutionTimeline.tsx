"use client";

import { StatusBadge } from "@/components/primitives";
import type { Execution } from "@/src/api/types/core";

export function ExecutionTimeline({
  executions,
  selectedId,
  onSelect,
}: {
  executions: Execution[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  const sorted = [...executions].sort((a, b) => b.attempt_number - a.attempt_number);
  return (
    <ul className="flex flex-col gap-2">
      {sorted.map((ex) => (
        <li key={ex.id}>
          <button
            type="button"
            className={`ol-ls w-full text-left ${selectedId === ex.id ? "is-on" : ""}`}
            onClick={() => onSelect(ex.id)}
          >
            <span className="ol-ls-code">#{ex.attempt_number}</span>
            <span className="ol-ls-name">{ex.key}</span>
            <StatusBadge status={ex.status} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function ExecutionEventList({
  events,
}: {
  events: { id: string; event_type: string; occurred_at: string; payload: Record<string, unknown> }[];
}) {
  if (!events.length) {
    return <p className="text-sm ol-muted">No governed tool events recorded for this attempt.</p>;
  }
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {events.map((e) => (
        <li key={e.id} className="border border-[var(--border)] rounded p-2">
          <div className="flex justify-between gap-2">
            <strong>{e.event_type}</strong>
            <span className="ol-muted text-xs">{e.occurred_at}</span>
          </div>
          <pre className="text-xs mt-1 overflow-auto max-h-24">{JSON.stringify(e.payload, null, 2)}</pre>
        </li>
      ))}
    </ul>
  );
}

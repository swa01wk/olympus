"use client";

import { useState } from "react";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import type { DomainEvent } from "@/lib/contracts/entity-types";

export function EventTimeline({ events }: { events: DomainEvent[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const sorted = [...events].sort((a, b) => b.sequence - a.sequence);

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs text-[var(--muted)]">{sorted.length} events</span>
        <FixtureBadge />
      </div>
      <ul className="space-y-2 font-mono text-xs">
        {sorted.map((e) => (
          <li key={e.id} className="rounded border border-[var(--border)] p-2">
            <button
              type="button"
              className="flex w-full flex-wrap items-center gap-2 text-left"
              onClick={() => setOpen(open === e.id ? null : e.id)}
            >
              <span className="text-[var(--muted)]">#{e.sequence}</span>
              <span>{e.event_type}</span>
              <span className="text-[var(--muted)]">{e.correlation_id?.slice(0, 8)}</span>
            </button>
            {open === e.id && (
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-[var(--raised)] p-2 text-[10px]">
                {JSON.stringify(e.payload, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

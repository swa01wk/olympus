"use client";

import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import type { DomainEvent } from "@/lib/contracts/entity-types";

export function LiveTimeline({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const eventsQ = useQuery({
    queryKey: [...qk.cycleEvents(cycleId), "timeline"],
    queryFn: async () => (await getServices()).deliveryCycles.events(cycleId),
    refetchInterval: 5000,
  });

  const items = (eventsQ.data?.items ?? []).slice(-12).reverse();

  return (
    <Panel title="Live Timeline" stateRail="running" actions={<FixtureBadge />}>
      <ul className="max-h-48 space-y-1 overflow-y-auto font-mono text-[11px]">
        {items.map((e: DomainEvent) => (
          <li key={e.id} className="flex gap-2 border-b border-[var(--border)]/50 py-1">
            <span className="text-[var(--muted)]">#{e.sequence}</span>
            <span>{e.event_type}</span>
            <span className="truncate text-[var(--muted)]">{e.aggregate_id.slice(0, 8)}</span>
          </li>
        ))}
        {items.length === 0 && <li className="text-[var(--muted)]">No events for cycle {cycleId.slice(0, 8)}…</li>}
      </ul>
      <p className="mt-2 text-[10px] text-[var(--muted)]">Project {projectId.slice(0, 8)} — fixture playback may append events.</p>
    </Panel>
  );
}

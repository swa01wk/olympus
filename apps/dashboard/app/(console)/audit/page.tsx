"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { EventTimeline } from "@/components/timeline/EventTimeline";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export default function AuditPage() {
  const search = useSearchParams();
  const projectId = search.get("project");
  const cycleId = search.get("cycle");

  const eventsQ = useQuery({
    queryKey: projectId ? ["projectEvents", projectId] : qk.cycleEvents(cycleId ?? ""),
    queryFn: async () => {
      if (projectId) return (await getServices()).events.forProject(projectId);
      if (cycleId) return (await getServices()).deliveryCycles.events(cycleId);
      return { items: [], next_after: null };
    },
    enabled: !!(projectId || cycleId),
  });

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Audit / Events</h1>
      {!projectId && !cycleId && (
        <p className="mb-4 text-xs text-[var(--muted)]">Add ?project= or ?cycle= to load events.</p>
      )}
      <EventTimeline events={eventsQ.data?.items ?? []} />
    </div>
  );
}

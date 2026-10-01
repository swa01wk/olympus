"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";

export default function ChangeRequestPage() {
  const { crId } = useParams<{ crId: string }>();
  const crQ = useQuery({
    queryKey: ["changeRequest", crId],
    queryFn: async () => (await getServices()).changeRequests.get(crId),
  });

  const cr = crQ.data;
  if (!cr) return <p>Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-xl font-semibold">{cr.key}</h1>
      <StatusBadge value={cr.status} />
      <FixtureBadge />
      <Panel title="Change request" stateRail="neutral" actions={<FixtureBadge />}>
        <p className="text-sm">{cr.title}</p>
        <p className="mt-2 text-xs text-[var(--muted)]">source {cr.source}</p>
      </Panel>
    </div>
  );
}

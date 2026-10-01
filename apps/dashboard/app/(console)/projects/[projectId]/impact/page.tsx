"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ImpactFlow } from "@/components/impact/ImpactFlow";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";

export default function ProjectImpactListPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const cycleId = useActiveCycleId(projectId);

  const impactQ = useQuery({
    queryKey: ["impact", cycleId],
    queryFn: async () => (await getServices()).impact.forCycle(cycleId!),
    enabled: !!cycleId,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Impact Analysis</h1>
      {impactQ.data ? (
        <>
          <Link href={`/impact/${impactQ.data.id}`} className="font-mono text-amber-400 underline">
            Open {impactQ.data.id.slice(0, 8)}…
          </Link>
          <ImpactFlow assessment={impactQ.data} />
        </>
      ) : (
        <Panel title="Impact" stateRail="neutral" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">No impact assessment for active cycle.</p>
        </Panel>
      )}
    </div>
  );
}

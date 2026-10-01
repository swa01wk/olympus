"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { LineageExplorer } from "@/components/lineage/LineageExplorer";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";

export default function ProjectLineagePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const cycleId = useActiveCycleId(projectId);
  const rootType = search.get("root_type") ?? "METHOD";
  const rootId = search.get("root_id");
  const direction = (search.get("direction") ?? "REVERSE") as "FORWARD" | "REVERSE";

  const lineageQ = useQuery({
    queryKey: ["lineage", rootType, rootId, direction],
    queryFn: async () =>
      (await getServices()).lineage.query({
        root_type: rootType,
        root_id: rootId!,
        direction,
        depth: 2,
      }),
    enabled: !!rootId,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Lineage</h1>
      <p className="text-xs text-[var(--muted)]">
        Project {projectId} · cycle {cycleId?.slice(0, 8)} — preset reverse from code symbol via query params.
      </p>
      {!rootId && (
        <p className="text-sm text-[var(--muted)]">
          Add ?root_type=METHOD&root_id=&lt;entity-id&gt;&direction=REVERSE or use fixture sample graph below.
        </p>
      )}
      {lineageQ.data && <LineageExplorer graph={lineageQ.data} />}
      {!rootId && <SampleLineageLoader />}
    </div>
  );
}

function SampleLineageLoader() {
  const sampleQ = useQuery({
    queryKey: ["lineage", "sample"],
    queryFn: async () =>
      (await getServices()).lineage.query({
        root_type: "METHOD",
        root_id: "00000000-0000-4000-8000-000000000001",
        direction: "REVERSE",
      }),
  });
  if (!sampleQ.data) return <p className="text-xs">Loading sample lineage…</p>;
  return <LineageExplorer graph={sampleQ.data} />;
}

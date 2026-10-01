"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { Panel } from "@/components/design/Panel";
import { KnowledgeChip } from "@/components/status/KnowledgeChip";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";

export default function BrownfieldPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const tab = search.get("tab") ?? "pipeline";
  const cycleId = useActiveCycleId(projectId);

  const discoveryQ = useQuery({
    queryKey: ["discovery", cycleId],
    queryFn: async () => (await getServices()).brownfield.discovery(cycleId!),
    enabled: !!cycleId,
  });
  const specsQ = useQuery({
    queryKey: ["recoveredSpecs", cycleId],
    queryFn: async () => (await getServices()).brownfield.recoveredSpecs(cycleId!),
    enabled: !!cycleId,
  });
  const readinessQ = useQuery({
    queryKey: ["readiness", cycleId],
    queryFn: async () => (await getServices()).brownfield.readiness(cycleId!),
    enabled: !!cycleId,
  });
  const baselinesQ = useQuery({
    queryKey: ["baselines", projectId],
    queryFn: async () => (await getServices()).brownfield.baselines(projectId),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Brownfield Intelligence</h1>
      <nav className="flex flex-wrap gap-2 text-xs">
        {(["pipeline", "facts", "recovered", "baselines", "readiness"] as const).map((t) => (
          <a
            key={t}
            href={`/projects/${projectId}/brownfield?tab=${t}`}
            className={`rounded border px-2 py-1 ${tab === t ? "border-amber-500" : "border-[var(--border)]"}`}
          >
            {t}
          </a>
        ))}
      </nav>

      {tab === "pipeline" && (
        <Panel title="Discovery pipeline" stateRail="running" actions={<FixtureBadge />}>
          <p className="text-xs">{discoveryQ.data?.status ?? "No discovery for active cycle"}</p>
        </Panel>
      )}
      {tab === "facts" && (
        <Panel title="Facts vs interpretation" stateRail="neutral" actions={<FixtureBadge />}>
          <div className="flex flex-wrap gap-2">
            <KnowledgeChip value="FACT" />
            <KnowledgeChip value="INFERENCE" />
            <KnowledgeChip value="UNCERTAINTY" />
          </div>
        </Panel>
      )}
      {tab === "recovered" && (
        <Panel title="Recovered specs" stateRail="waiting" actions={<FixtureBadge />}>
          <ul className="space-y-2 text-sm">
            {specsQ.data?.map((s) => (
              <li key={s.id} className="rounded border border-dashed border-amber-800/50 p-2">
                {s.key} — {s.knowledge_class}{" "}
                <span className="text-[var(--muted)]">confidence {s.confidence}</span>
                {s.review_status !== "PROMOTED" && <span className="ml-2 text-amber-400">watermark</span>}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "baselines" && (
        <Panel title="Baselines" stateRail="complete" actions={<FixtureBadge />}>
          <p className="mb-2 text-xs">{baselinesQ.data?.length ?? 0} behavioral baselines</p>
          <ul className="font-mono text-[11px]">
            {baselinesQ.data?.slice(0, 12).map((b) => (
              <li key={b.id}>
                {b.key} — {b.status}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "readiness" && readinessQ.data && (
        <Panel title="Readiness" stateRail="complete" actions={<FixtureBadge />}>
          <p className="text-sm">State: {readinessQ.data.state}</p>
          <ul className="mt-2 text-xs">
            {readinessQ.data.metrics?.map((m) => (
              <li key={m.name}>
                {m.name}: {m.value}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

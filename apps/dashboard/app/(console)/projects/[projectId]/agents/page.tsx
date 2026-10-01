"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { AgentOpsBoard } from "@/components/agents/AgentOpsBoard";
import { ActionGovernancePipeline } from "@/components/governance/ActionGovernancePipeline";
import { ActionTimeline } from "@/components/governance/ActionTimeline";
import { PendingCapability } from "@/components/states/PendingCapability";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";
import { qk } from "@/lib/query/keys";

export default function AgentsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const tab = search.get("tab") ?? "capabilities";
  const cycleId = useActiveCycleId(projectId);

  const execQ = useQuery({
    queryKey: qk.cycleExecutions(cycleId ?? ""),
    queryFn: async () => (await getServices()).executions.listByCycle(cycleId!),
    enabled: !!cycleId && tab === "capabilities",
  });

  const actionsQ = useQuery({
    queryKey: ["actions", projectId, cycleId],
    queryFn: async () =>
      (await getServices()).actions.list({
        project_id: projectId,
        delivery_cycle_id: cycleId!,
      }),
    enabled: !!cycleId && (tab === "actions" || tab === "capabilities"),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Agent Operations</h1>
      <nav className="flex gap-2 text-xs">
        {(["capabilities", "runtime", "actions"] as const).map((t) => (
          <a
            key={t}
            href={`/projects/${projectId}/agents?tab=${t}${cycleId ? `&cycle=${cycleId}` : ""}`}
            className={`rounded border px-2 py-1 capitalize ${tab === t ? "border-amber-500 text-amber-300" : "border-[var(--border)]"}`}
          >
            {t}
          </a>
        ))}
      </nav>

      {tab === "capabilities" && execQ.data && (
        <AgentOpsBoard executions={execQ.data} actions={actionsQ.data ?? []} />
      )}
      {tab === "runtime" && (
        <div className="space-y-3">
          <PendingCapability capabilityId="GET /runtime/workers" backendPhase="07" />
          <PendingCapability capabilityId="GET /runtime/model-aliases" backendPhase="07" />
        </div>
      )}
      {tab === "actions" && actionsQ.data && (
        <div className="space-y-4">
          <ActionTimeline actions={actionsQ.data} />
          <ActionGovernancePipeline
            action={actionsQ.data.find((a) => a.status === "DENIED" || a.status === "PENDING_APPROVAL")}
          />
        </div>
      )}
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { AssuranceProgress } from "@/components/control-plane/AssuranceProgress";
import { ExecutionManagerPanel } from "@/components/control-plane/ExecutionManagerPanel";
import { IntegrationReadiness } from "@/components/control-plane/IntegrationReadiness";
import { PolicyPanel } from "@/components/control-plane/PolicyPanel";
import { ReleaseReadiness } from "@/components/control-plane/ReleaseReadiness";
import { SchedulerPanel } from "@/components/control-plane/SchedulerPanel";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";
import { qk } from "@/lib/query/keys";
import { DecisionExplainer } from "@/components/transparency/DecisionExplainer";
import { OlympusApiError } from "@/lib/api/errors";

export default function ControlPlanePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const cycleId = useActiveCycleId(projectId);

  const controlQ = useQuery({
    queryKey: [...qk.cycle(cycleId ?? ""), "controlPlane"],
    queryFn: async () => (await getServices()).controlPlane.forCycle(cycleId!),
    enabled: !!cycleId,
  });

  const tasksQ = useQuery({
    queryKey: qk.cycleTasks(cycleId ?? ""),
    queryFn: async () => (await getServices()).tasks.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const execQ = useQuery({
    queryKey: qk.cycleExecutions(cycleId ?? ""),
    queryFn: async () => (await getServices()).executions.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const actionsQ = useQuery({
    queryKey: ["actions", projectId, cycleId],
    queryFn: async () =>
      (await getServices()).actions.list({
        project_id: projectId,
        delivery_cycle_id: cycleId!,
      }),
    enabled: !!cycleId,
  });

  const icsQ = useQuery({
    queryKey: qk.ics(cycleId ?? ""),
    queryFn: async () => (await getServices()).integration.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const icId = icsQ.data?.find((ic) => ic.status !== "SUPERSEDED")?.id;
  const gatesQ = useQuery({
    queryKey: qk.gates(icId ?? ""),
    queryFn: async () => (await getServices()).assurance.gatesForIc(icId!),
    enabled: !!icId,
  });

  const eligQ = useQuery({
    queryKey: qk.releaseEligibility(cycleId ?? ""),
    queryFn: async () => {
      try {
        return await (await getServices()).release.eligibility(cycleId!);
      } catch (e) {
        if (e instanceof OlympusApiError && e.code === "NOT_EVALUATED") return null;
        throw e;
      }
    },
    enabled: !!cycleId,
  });

  const explainQ = useQuery({
    queryKey: qk.controlExplain("delivery_cycle", cycleId ?? ""),
    queryFn: async () =>
      (await getServices()).controlPlane.explain("delivery_cycle", cycleId!),
    enabled: !!cycleId,
  });

  if (!cycleId) return <p>Loading…</p>;
  const view = controlQ.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Control Plane Inspector</h1>
      <DecisionExplainer decision={explainQ.data ?? null} />
      <p className="text-xs text-[var(--muted)]">Cycle {cycleId.slice(0, 8)}… — server-composed M-22 view</p>
      {view && tasksQ.data && (
        <SchedulerPanel
          projectId={projectId}
          cycleId={cycleId}
          tasks={tasksQ.data}
          scheduler={view.scheduler}
        />
      )}
      {view && execQ.data && (
        <ExecutionManagerPanel executions={execQ.data} manager={view.execution_manager} />
      )}
      {view && actionsQ.data && (
        <PolicyPanel actions={actionsQ.data} policy={view.policy} />
      )}
      {view && icsQ.data && (
        <IntegrationReadiness
          projectId={projectId}
          cycleId={cycleId}
          ics={icsQ.data}
          integration={view.integration}
        />
      )}
      {view && (
        <AssuranceProgress gates={gatesQ.data ?? []} assurance={view.assurance} />
      )}
      {view && (
        <ReleaseReadiness
          projectId={projectId}
          eligibility={eligQ.data ?? null}
          release={view.release}
        />
      )}
    </div>
  );
}

"use client";

import { useParams } from "next/navigation";
import { useQueries, useQuery } from "@tanstack/react-query";
import { ActiveExecutionPanel } from "@/components/command-center/ActiveExecutionPanel";
import { ControlPlaneStrip } from "@/components/command-center/ControlPlaneStrip";
import { CycleHeader } from "@/components/command-center/CycleHeader";
import { LiveTimeline } from "@/components/command-center/LiveTimeline";
import { MacroForge } from "@/components/command-center/MacroForge";
import { StatusTiles } from "@/components/command-center/StatusTiles";
import { LifecycleForge } from "@/components/lifecycle/LifecycleForge";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";
import { qk } from "@/lib/query/keys";
import { buildForgeStages } from "@/lib/view-models/lifecycle";
import { buildMacroBands } from "@/lib/view-models/macro-forge";
import { isExecutionActive } from "@/lib/utils/execution-active";
import { OlympusApiError } from "@/lib/api/errors";
import type { TaskContract } from "@/lib/contracts/entity-types";

export default function CommandCenterPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const cycleId = useActiveCycleId(projectId);

  const projectQ = useQuery({
    queryKey: qk.project(projectId),
    queryFn: async () => (await getServices()).projects.get(projectId),
  });

  const cycleQ = useQuery({
    queryKey: qk.cycle(cycleId ?? ""),
    queryFn: async () => (await getServices()).deliveryCycles.get(cycleId!),
    enabled: !!cycleId,
  });

  const previewsQ = useQuery({
    queryKey: [...qk.cycle(cycleId ?? ""), "transitions"],
    queryFn: async () => (await getServices()).deliveryCycles.nextTransitions(cycleId!),
    enabled: !!cycleId,
  });

  const overviewQ = useQuery({
    queryKey: [...qk.cycle(cycleId ?? ""), "overview"],
    queryFn: async () => (await getServices()).views.cycleOverview(cycleId!),
    enabled: !!cycleId,
  });

  const controlQ = useQuery({
    queryKey: [...qk.cycle(cycleId ?? ""), "controlPlane"],
    queryFn: async () => (await getServices()).views.controlPlane(cycleId!),
    enabled: !!cycleId,
  });

  const execQ = useQuery({
    queryKey: qk.cycleExecutions(cycleId ?? ""),
    queryFn: async () => (await getServices()).executions.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const tasksQ = useQuery({
    queryKey: qk.cycleTasks(cycleId ?? ""),
    queryFn: async () => (await getServices()).tasks.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const releasesQ = useQuery({
    queryKey: qk.releases(projectId),
    queryFn: async () => (await getServices()).release.list(projectId),
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

  const inboxQ = useQuery({
    queryKey: qk.inbox(),
    queryFn: async () => (await getServices()).inbox.list(),
  });

  const runningTasks = tasksQ.data?.filter((t) => t.status === "RUNNING") ?? [];
  const contractQueries = useQueries({
    queries: runningTasks.map((t) => ({
      queryKey: ["contract", t.id],
      queryFn: async () => (await getServices()).tasks.contract(t.id),
    })),
  });
  const contractsByTask: Record<string, TaskContract | undefined> = {};
  runningTasks.forEach((t, i) => {
    contractsByTask[t.id] = contractQueries[i]?.data;
  });

  const cycle = cycleQ.data;
  const running = execQ.data?.filter((e) => isExecutionActive(e.status)).length ?? 0;
  const stages =
    cycle && previewsQ.data
      ? buildForgeStages(cycle.type, cycle.state, previewsQ.data, { runningExecutions: running })
      : [];
  const macroBands =
    cycle && previewsQ.data
      ? buildMacroBands(cycle.type, cycle.state, previewsQ.data, { runningExecutions: running })
      : [];

  const targetRelease = releasesQ.data?.find(
    (r) => r.delivery_cycle_id === cycleId && r.status === "DRAFT",
  )?.key;

  const eligibility = eligQ.data ?? null;

  if (!cycleId) return <p className="text-[var(--muted)]">Loading cycle context…</p>;

  return (
    <div className="space-y-6">
      {projectQ.data && cycle && (
        <CycleHeader
          project={projectQ.data}
          cycle={cycle}
          projectId={projectId}
          targetReleaseKey={targetRelease}
        />
      )}

      {cycle && macroBands.length > 0 && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase text-[var(--muted)]">Macro forge</h2>
          <MacroForge bands={macroBands} />
        </section>
      )}

      {cycle && stages.length > 0 && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase text-[var(--muted)]">Lifecycle</h2>
          <LifecycleForge stages={stages} variant="compact" />
        </section>
      )}

      {controlQ.data && (
        <ControlPlaneStrip projectId={projectId} cycleId={cycleId} view={controlQ.data} />
      )}

      {execQ.data && tasksQ.data && (
        <ActiveExecutionPanel
          executions={execQ.data}
          tasks={tasksQ.data}
          contractsByTask={contractsByTask}
        />
      )}

      {tasksQ.data && execQ.data && (
        <StatusTiles
          projectId={projectId}
          cycleId={cycleId}
          tasks={tasksQ.data}
          executions={execQ.data}
          inboxCount={inboxQ.data?.length ?? 0}
          eligibility={eligibility}
          blockedCount={overviewQ.data?.blocked_tasks ?? 0}
        />
      )}

      <LiveTimeline projectId={projectId} cycleId={cycleId} />
    </div>
  );
}

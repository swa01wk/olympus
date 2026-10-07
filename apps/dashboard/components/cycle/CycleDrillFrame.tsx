"use client";

import { AttentionStrip } from "@/components/cycle/AttentionStrip";
import { CycleHeader } from "@/components/cycle/CycleHeader";
import { LaneStrip } from "@/components/cycle/LaneStrip";
import { AppShell } from "@/components/shell/AppShell";
import { EmptyState } from "@/components/primitives";
import { cycleMapPath } from "@/lib/cycle-url";
import { invalidateCycleQueries } from "@/src/api/hooks/invalidate-cycle";
import {
  useAttentionQueue,
  useControlPlaneGraph,
  useDeliveryCycle,
  useDeliveryCycles,
  useProject,
  useTasks,
} from "@/src/api/hooks/use-olympus-queries";
import { useCycleEventStream } from "@/src/api/sse/use-cycle-event-stream";
import type { ScreenId } from "@/src/control-plane/lanes";
import { useOperatorDialogs } from "@/components/providers/OperatorDialogsProvider";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, type ReactNode } from "react";

export function CycleDrillFrame({
  projectId,
  cycleId,
  activeScreen,
  children,
}: {
  projectId: string;
  cycleId: string;
  activeScreen: ScreenId;
  children: ReactNode;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const operator = useOperatorDialogs();
  const project = useProject(projectId);
  const cycles = useDeliveryCycles(projectId);
  const cycle = useDeliveryCycle(cycleId || undefined);
  const tasks = useTasks(cycleId || undefined);
  const cp = useControlPlaneGraph(cycleId || undefined);
  const attention = useAttentionQueue(cycleId || undefined);

  const taskIds = useMemo(() => (tasks.data ?? []).map((t) => t.id), [tasks.data]);

  const invalidate = useCallback(() => {
    if (cycleId) invalidateCycleQueries(queryClient, cycleId, taskIds);
  }, [queryClient, cycleId, taskIds]);

  const stream = useCycleEventStream(cycleId || undefined, { invalidate, enabled: Boolean(cycleId) });

  const laneFlags = useMemo(() => {
    const flags: Partial<Record<string, string>> = {};
    const graph = cp.graph;
    for (const item of attention) {
      const node = graph?.nodes.find(
        (n) => n.status === item.uiStatusKey || n.ref.includes(item.id.slice(0, 8)),
      );
      if (node) flags[node.lane] = item.uiStatusKey;
    }
    return flags;
  }, [attention, cp.graph]);

  const onCycleChange = (id: string) => {
    router.push(cycleMapPath(projectId, id));
  };

  if (!cycleId) {
    return (
      <AppShell
        project={project.data}
        cycles={cycles.data ?? []}
        cycleId=""
        onCycleChange={onCycleChange}
        stream={stream}
      >
        <EmptyState
          title="No delivery cycle"
          description="Pick a cycle from the header or open the control-plane map."
        />
      </AppShell>
    );
  }

  if (cycle.isLoading && !cycle.data) {
    return (
      <AppShell
        project={project.data}
        cycles={cycles.data ?? []}
        cycleId={cycleId}
        onCycleChange={onCycleChange}
        stream={stream}
        laneFlags={laneFlags}
      >
        <p className="ol-muted">Loading cycle…</p>
      </AppShell>
    );
  }

  if (!cycle.data) {
    return (
      <AppShell
        project={project.data}
        cycles={cycles.data ?? []}
        cycleId={cycleId}
        onCycleChange={onCycleChange}
        stream={stream}
        laneFlags={laneFlags}
      >
        <EmptyState title="Cycle unavailable" description="Could not load this delivery cycle." />
      </AppShell>
    );
  }

  return (
    <AppShell
      project={project.data}
      cycles={cycles.data ?? []}
      cycleId={cycleId}
      onCycleChange={onCycleChange}
      stream={stream}
      laneFlags={laneFlags}
    >
      <div className="ol-screen">
        <CycleHeader cycle={cycle.data} />
        <LaneStrip projectId={projectId} cycleId={cycleId} cycle={cycle.data} activeScreen={activeScreen} />
        <AttentionStrip
          cycle={cycle.data}
          items={attention}
          onInspect={(item) => {
            operator.openAttentionItem(item);
            router.push(cycleMapPath(projectId, cycleId));
          }}
          onWhy={() => router.push(cycleMapPath(projectId, cycleId))}
        />
        {children}
        <p className="text-xs ol-muted">
          <Link className="ol-idlink" href={cycleMapPath(projectId, cycleId)}>
            Back to control-plane map
          </Link>
        </p>
      </div>
    </AppShell>
  );
}

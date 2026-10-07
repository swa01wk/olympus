"use client";

import { AttentionStrip } from "@/components/cycle/AttentionStrip";
import { CycleHeader } from "@/components/cycle/CycleHeader";
import { ControlPlaneGraphView } from "@/components/graph/ControlPlaneGraphView";
import { ObjectInspector } from "@/components/inspector/ObjectInspector";
import { AppShell } from "@/components/shell/AppShell";
import { Panel } from "@/components/primitives";
import { cycleMapPath, parseCycleMapSearch } from "@/lib/cycle-url";
import { commandsForCycle, whyForCycleState, whyForNode } from "@/lib/inspector-why";
import { useMediaQuery } from "@/lib/use-media-query";
import { screenHref } from "@/lib/nav-hrefs";
import { invalidateCycleQueries } from "@/src/api/hooks/invalidate-cycle";
import {
  useAttentionQueue,
  useControlPlaneGraph,
  useDeliveryCycles,
  useProject,
} from "@/src/api/hooks/use-olympus-queries";
import { useCycleEventStream } from "@/src/api/sse/use-cycle-event-stream";
import type { LensId } from "@/src/control-plane/lanes";
import { laneForCycleState, ribbonStages, stageIndex, stagesForCycleType } from "@/src/control-plane/stage-lanes";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AttentionItem } from "@/src/control-plane/attention";
import { useOperatorDialogs } from "@/components/providers/OperatorDialogsProvider";
import { StreamDisconnectedNotice } from "@/components/truth/StreamDisconnectedNotice";
import { EmptyState } from "@/components/primitives";
import type { CommandPreview } from "@/components/inspector/CommandList";

export function CycleMapScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const parsed = parseCycleMapSearch(searchParams);
  const selectedId = parsed.selected;
  const lens = (parsed.lens ?? "lifecycle") as LensId;
  const narrow = useMediaQuery("(max-width: 719px)");
  const view = parsed.view === "list" || narrow ? "list" : "graph";

  const queryClient = useQueryClient();
  const operator = useOperatorDialogs();
  const openedApprovalFromQuery = useRef<string | null>(null);
  const approvalFromQuery = searchParams.get("approval");
  useEffect(() => {
    if (!approvalFromQuery || openedApprovalFromQuery.current === approvalFromQuery) return;
    openedApprovalFromQuery.current = approvalFromQuery;
    operator.openApproval(approvalFromQuery);
  }, [approvalFromQuery, operator]);
  const project = useProject(projectId);
  const cycles = useDeliveryCycles(projectId);
  const cp = useControlPlaneGraph(cycleId);
  const attention = useAttentionQueue(cycleId);

  const taskIds = useMemo(() => {
    return (cp.graph?.nodes ?? [])
      .filter((n) => n.kind === "Task")
      .map((n) => n.id.split(":")[1])
      .filter(Boolean) as string[];
  }, [cp.graph]);

  const invalidate = useCallback(() => {
    invalidateCycleQueries(queryClient, cycleId, taskIds);
  }, [queryClient, cycleId, taskIds]);

  const stream = useCycleEventStream(cycleId, { invalidate });

  const [focusEdge, setFocusEdge] = useState<string | null>(null);
  const [showCycleWhy, setShowCycleWhy] = useState(false);

  const setSearch = (patch: Partial<{ selected?: string; lens: LensId; view: "graph" | "list" }>) => {
    router.replace(
      cycleMapPath(projectId, cycleId, {
        selected: patch.selected !== undefined ? patch.selected : selectedId,
        lens: patch.lens ?? lens,
        view: patch.view ?? view,
      }),
    );
  };

  const cycle = cp.cycle;
  const graph = cp.graph;

  const nodesById = useMemo(() => {
    const m = new Map<string, NonNullable<typeof graph>["nodes"][number]>();
    for (const n of graph?.nodes ?? []) m.set(n.id, n);
    return m;
  }, [graph]);

  const selectedNode = selectedId ? nodesById.get(selectedId) : undefined;

  const stageIdx = cycle ? Math.max(0, stageIndex(cycle.type, cycle.state)) : 0;
  const ribbon = cycle ? ribbonStages(cycle.type, cycle.state) : [];
  const spineStages = cycle
    ? stagesForCycleType(cycle.type).map((s) => ({ state: s.state, laneId: s.laneId }))
    : [];
  const currentLane = cycle ? laneForCycleState(cycle.type, cycle.state)?.laneId : undefined;

  const laneFlags = useMemo(() => {
    const flags: Partial<Record<string, string>> = {};
    for (const item of attention) {
      const node = graph?.nodes.find((n) => n.status === item.uiStatusKey || n.ref.includes(item.id.slice(0, 8)));
      if (node) flags[node.lane] = item.uiStatusKey;
    }
    return flags;
  }, [attention, graph]);

  const why = showCycleWhy && cycle && cp.overview
    ? whyForCycleState(cycle.state, cp.overview.next_transitions)
    : selectedNode
      ? whyForNode(selectedNode, { cycleTransitions: cp.overview?.next_transitions })
      : undefined;

  const commands =
    showCycleWhy && cycle ? commandsForCycle(cycle.allowed_commands, cycle.state) : [];

  const onCycleCommand = (c: CommandPreview) => {
    if (!cycle?.id || !c.cycleCommand || c.enabled === false) return;
    operator.openCycleCommand({
      cycleId,
      command: c.cycleCommand.command,
      expectedState: c.cycleCommand.expectedState,
      label: c.label,
    });
  };

  const onCycleChange = (id: string) => {
    router.push(cycleMapPath(projectId, id, { lens, view }));
  };

  const onOpenLane = (laneId: string) => {
    const map: Record<string, Parameters<typeof screenHref>[0]> = {
      intent: "S03",
      work: "S04",
      exec: "S05",
      code: "S06",
      evidence: "S09",
      outcome: "S10",
    };
    const screen = map[laneId];
    if (screen) router.push(screenHref(screen, projectId, cycleId));
  };

  const onInspectAttention = (item: AttentionItem) => {
    operator.openAttentionItem(item);
    const node = graph?.nodes.find((n) => n.ref.includes(item.id.slice(0, 6)) || n.status === item.uiStatusKey);
    if (node) setSearch({ selected: node.id });
  };

  if (cp.isLoading && !cycle) {
    return (
      <AppShell
        project={project.data}
        cycles={cycles.data ?? []}
        cycleId={cycleId}
        onCycleChange={onCycleChange}
        stream={stream}
      >
        <p className="ol-muted">Loading control plane…</p>
      </AppShell>
    );
  }

  if (!cycle || !graph) {
    return (
      <AppShell
        project={project.data}
        cycles={cycles.data ?? []}
        cycleId={cycleId}
        onCycleChange={onCycleChange}
        stream={stream}
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
        <CycleHeader cycle={cycle} projectId={projectId} />
        <AttentionStrip
          cycle={cycle}
          items={attention}
          onInspect={onInspectAttention}
          onWhy={() => setShowCycleWhy(true)}
        />
        {stream.state === "disconnected" && (
          <StreamDisconnectedNotice lastRefreshAt={stream.lastRefreshAt} onRefetch={() => void cp.refetch()} />
        )}
        <div className="ol-mapgrid">
          <Panel className="ol-mappanel" pad={false}>
            <ControlPlaneGraphView
              graph={graph}
              stages={spineStages}
              stageIndex={stageIdx}
              currentLaneId={currentLane ?? ribbon[stageIdx]?.laneId ?? "intent"}
              lens={lens}
              onLens={(l) => setSearch({ lens: l })}
              view={view}
              onView={(v) => setSearch({ view: v })}
              selectedId={selectedId}
              onSelect={(id) => {
                setShowCycleWhy(false);
                setSearch({ selected: id });
              }}
              onOpenLane={(l) => onOpenLane(l)}
              attention={attention}
              focusEdgeKey={focusEdge}
            />
          </Panel>
          <ObjectInspector
            node={showCycleWhy ? undefined : selectedNode}
            edges={graph.edges}
            nodesById={nodesById}
            why={why}
            commands={commands}
            projectId={projectId}
            cycleId={cycleId}
            lens={lens}
            onSelect={(id) => setSearch({ selected: id })}
            onHoverEdge={setFocusEdge}
            onCommand={onCycleCommand}
          />
        </div>
        {showCycleWhy && (
          <p className="text-sm ol-muted">
            Showing cycle transition guards.{" "}
            <button type="button" className="ol-idlink" onClick={() => setShowCycleWhy(false)}>
              Clear
            </button>
          </p>
        )}
      </div>
    </AppShell>
  );
}

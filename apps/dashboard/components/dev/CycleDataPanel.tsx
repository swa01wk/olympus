"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { EmptyState, KV, Panel, StatusBadge } from "@/components/primitives";
import { StreamStatus } from "@/components/shell/StreamStatus";
import { getApiBaseUrl } from "@/src/api/config";
import { isApiError } from "@/src/api/client";
import { invalidateCycleQueries } from "@/src/api/hooks/invalidate-cycle";
import {
  useAttentionQueue,
  useControlPlaneGraph,
  useProjects,
  useTasks,
} from "@/src/api/hooks/use-olympus-queries";
import { useCycleEventStream } from "@/src/api/sse/use-cycle-event-stream";

export function CycleDataPanel({ cycleId }: { cycleId: string }) {
  const queryClient = useQueryClient();
  const tasks = useTasks(cycleId);
  const taskIds = (tasks.data ?? []).map((t) => t.id);
  const invalidate = useCallback(() => {
    invalidateCycleQueries(queryClient, cycleId, taskIds);
  }, [queryClient, cycleId, taskIds]);
  const stream = useCycleEventStream(cycleId, { invalidate });
  const cp = useControlPlaneGraph(cycleId);
  const attention = useAttentionQueue(cycleId);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StreamStatus stream={stream} />
        <span className="ol-sha">API {getApiBaseUrl()}</span>
      </div>

      {cp.isLoading && <p className="ol-muted text-sm">Loading cycle data…</p>}
      {cp.isError && (
        <EmptyState
          title="Could not load cycle"
          description="Set NEXT_PUBLIC_OLYMPUS_API_URL and a bearer token (localStorage olympus_api_token or NEXT_PUBLIC_OLYMPUS_API_TOKEN)."
        />
      )}

      {cp.cycle && (
        <Panel title={cp.cycle.objective} sub={`${cp.cycle.key} · ${cp.cycle.type} · ${cp.cycle.state}`}>
          <KV
            rows={[
              ["Tasks", String(cp.graph?.nodes.filter((n) => n.kind === "Task" || n.kind === "TaskGroup").length ?? 0)],
              ["Executions", String(cp.graph?.nodes.filter((n) => n.kind.startsWith("Execution")).length ?? 0)],
              ["Graph edges", String(cp.graph?.edges.length ?? 0)],
              ["Attention", attention[0]?.headline ?? "Nothing needs you"],
            ]}
          />
          {attention[0] && (
            <div className="mt-3">
              <StatusBadge status={attention[0].uiStatusKey} label={attention[0].kind} />
            </div>
          )}
        </Panel>
      )}

      {cp.graph && cp.graph.nodes.length > 0 && (
        <Panel title="Graph nodes (adapter preview)" sub="Phase 4 renders lanes">
          <ul className="text-sm space-y-1 m-0 p-0 list-none">
            {cp.graph.nodes.slice(0, 12).map((n) => (
              <li key={n.id} className="font-mono text-xs">
                [{n.lane}] {n.kind} {n.ref}{" "}
                <StatusBadge status={n.status} size="sm" />
                {n.future ? " (obligation)" : ""}
              </li>
            ))}
            {cp.graph.nodes.length > 12 && (
              <li className="ol-muted text-xs">+{cp.graph.nodes.length - 12} more</li>
            )}
          </ul>
        </Panel>
      )}
    </div>
  );
}

export function ProjectsPicker({
  cycleId,
  onCycleId,
}: {
  cycleId: string;
  onCycleId: (id: string) => void;
}) {
  const projects = useProjects();
  const firstProject = projects.data?.[0];

  if (projects.isError && isApiError(projects.error)) {
    return (
      <p className="text-sm text-[var(--failure)]">
        {projects.error.code}: {projects.error.message}
      </p>
    );
  }

  return (
    <Panel title="Projects" sub="Pick a cycle id for Phase 3 smoke test">
      <p className="text-sm ol-muted mb-2">
        Enter a delivery cycle UUID below, or load from the first project once authenticated.
      </p>
      <input
        className="w-full h-9 px-3 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] font-mono text-xs"
        value={cycleId}
        onChange={(e) => onCycleId(e.target.value)}
        placeholder="delivery-cycle-uuid"
        aria-label="Delivery cycle id"
      />
      {firstProject && (
        <p className="text-xs ol-muted mt-2">First project: {firstProject.key} ({firstProject.id})</p>
      )}
    </Panel>
  );
}

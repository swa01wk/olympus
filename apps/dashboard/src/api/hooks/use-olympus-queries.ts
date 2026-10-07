"use client";

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useMemo } from "react";
import { isApiError } from "@/src/api/client";
import { sendCommand, sendDeliveryCycleCommand } from "@/src/api/commands";
import { queryKeys } from "@/src/api/query-keys";
import {
  fetchActorMe,
  fetchControlPlaneSummary,
  fetchCycleOverview,
  fetchDeliveryCycle,
  fetchDeliveryCycles,
  fetchExecutions,
  fetchInbox,
  fetchIntegrationCandidates,
  fetchObligations,
  fetchProject,
  fetchProjectOverview,
  fetchProjects,
  fetchTasks,
} from "@/src/api/resources";
import { buildControlPlaneGraph } from "@/src/control-plane/build-graph";
import type { ControlPlaneGraph } from "@/src/control-plane/graph-types";
import {
  attentionFromInboxRow,
  sortAttentionItems,
  type AttentionItem,
} from "@/src/control-plane/attention";
import type {
  ControlPlaneSummaryView,
  CycleOverviewView,
  DeliveryCycle,
  Execution,
} from "@/src/api/types/core";

export function useActorMe(enabled = true) {
  return useQuery({
    queryKey: queryKeys.actor,
    queryFn: fetchActorMe,
    enabled,
    retry: (count, err) => !(isApiError(err) && err.status === 401) && count < 2,
  });
}

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects.all, queryFn: fetchProjects });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.projects.detail(projectId ?? ""),
    queryFn: () => fetchProject(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useProjectOverview(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.projectOverview(projectId ?? ""),
    queryFn: () => fetchProjectOverview(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useDeliveryCycles(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cycles.list(projectId ?? ""),
    queryFn: () => fetchDeliveryCycles(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useDeliveryCycle(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cycles.detail(cycleId ?? ""),
    queryFn: () => fetchDeliveryCycle(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useCycleOverview(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cycles.overview(cycleId ?? ""),
    queryFn: () => fetchCycleOverview(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useControlPlaneSummary(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cycles.controlPlane(cycleId ?? ""),
    queryFn: () => fetchControlPlaneSummary(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useInbox(params?: { projectId?: string; cycleId?: string }) {
  return useQuery({
    queryKey: queryKeys.inbox(params),
    queryFn: () => fetchInbox(params),
  });
}

export function useAttentionQueue(cycleId?: string) {
  const inbox = useInbox(cycleId ? { cycleId } : undefined);
  return useMemo(() => {
    const rows = (inbox.data ?? []).filter(
      (item) => !cycleId || item.delivery_cycle_id === cycleId || item.delivery_cycle_id == null,
    );
    const items: AttentionItem[] = rows.map((r) => attentionFromInboxRow(r));
    return sortAttentionItems(items);
  }, [inbox.data, cycleId]);
}

export function useTasks(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.tasks.byCycle(cycleId ?? ""),
    queryFn: () => fetchTasks(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useExecutionsForTasks(taskIds: string[]) {
  return useQueries({
    queries: taskIds.map((taskId) => ({
      queryKey: queryKeys.executions.byTask(taskId),
      queryFn: () => fetchExecutions(taskId),
      enabled: Boolean(taskId),
    })),
  });
}

export function useIntegrationCandidates(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.integration.candidates(cycleId ?? ""),
    queryFn: () => fetchIntegrationCandidates(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useObligations(icId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.integration.obligations(icId ?? ""),
    queryFn: () => fetchObligations(icId!),
    enabled: Boolean(icId),
  });
}

export type ControlPlaneGraphQuery = {
  graph: ControlPlaneGraph | undefined;
  cycle: DeliveryCycle | undefined;
  summary: ControlPlaneSummaryView | undefined;
  overview: CycleOverviewView | undefined;
  isLoading: boolean;
  isError: boolean;
  refetch: () => Promise<void>;
};

export function useControlPlaneGraph(cycleId: string | undefined): ControlPlaneGraphQuery {
  const cycle = useDeliveryCycle(cycleId);
  const tasks = useTasks(cycleId);
  const summary = useControlPlaneSummary(cycleId);
  const overview = useCycleOverview(cycleId);
  const ics = useIntegrationCandidates(cycleId);
  const taskIds = useMemo(() => (tasks.data ?? []).map((t) => t.id), [tasks.data]);
  const execQueries = useExecutionsForTasks(taskIds);
  const latestIcId = ics.data?.[ics.data.length - 1]?.id;
  const obligations = useObligations(latestIcId);

  const executions = useMemo(() => {
    const all: Execution[] = [];
    for (const q of execQueries) {
      if (q.data) all.push(...q.data);
    }
    return all;
  }, [execQueries]);

  const graph = useMemo(() => {
    if (!cycle.data) return undefined;
    return buildControlPlaneGraph({
      cycle: cycle.data,
      tasks: tasks.data ?? [],
      executions,
      integrationCandidates: ics.data ?? [],
      obligations: obligations.data,
    });
  }, [cycle.data, tasks.data, executions, ics.data, obligations.data]);

  const isLoading =
    cycle.isLoading ||
    tasks.isLoading ||
    summary.isLoading ||
    ics.isLoading ||
    execQueries.some((q) => q.isLoading);
  const isError =
    cycle.isError ||
    tasks.isError ||
    summary.isError ||
    ics.isError ||
    execQueries.some((q) => q.isError);

  const refetch = async () => {
    await Promise.all([
      cycle.refetch(),
      tasks.refetch(),
      summary.refetch(),
      overview.refetch(),
      ics.refetch(),
      obligations.refetch(),
      ...execQueries.map((q) => q.refetch()),
    ]);
  };

  return {
    graph,
    cycle: cycle.data,
    summary: summary.data,
    overview: overview.data,
    isLoading,
    isError,
    refetch,
  };
}

export function useDeliveryCycleCommandMutation(cycleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: { command: string; expectedState: string; payload?: Record<string, unknown> | null }) =>
      sendDeliveryCycleCommand(cycleId, vars.command, vars.expectedState, vars.payload),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.detail(cycleId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.overview(cycleId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.controlPlane(cycleId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.transitions(cycleId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.inboxRoot });
    },
  });
}

export { sendCommand };

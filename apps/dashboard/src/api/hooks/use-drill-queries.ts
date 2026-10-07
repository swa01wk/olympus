"use client";

import { taskPlanBodyToDag, type TaskPlanBody } from "@/lib/task-plan-dag";
import { isApiError } from "@/src/api/client";
import { queryKeys } from "@/src/api/query-keys";
import {
  fetchAgentActivity,
  fetchAuditForTarget,
  fetchAuditVerify,
  fetchCodeEntities,
  fetchConnectors,
  fetchCycleKnowledge,
  fetchCycleOutcome,
  fetchExecution,
  fetchExecutionEvents,
  fetchFeatureLineage,
  fetchIcAssurance,
  fetchLatestImpactAssessment,
  fetchProjectCoverage,
  fetchProjectFeatures,
  fetchProjectRepository,
  fetchProjectReleases,
  fetchReleaseEligibility,
  fetchTask,
  fetchTaskContract,
  fetchTaskDag,
  fetchTaskEligibility,
  fetchTaskPlan,
  fetchTaskPlans,
} from "@/src/api/resources";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

export function useProjectCoverage(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.coverage(projectId ?? ""),
    queryFn: () => fetchProjectCoverage(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useProjectRepositoryView(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.repository(projectId ?? ""),
    queryFn: () => fetchProjectRepository(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useTask(taskId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.tasks.detail(taskId ?? ""),
    queryFn: () => fetchTask(taskId!),
    enabled: Boolean(taskId),
  });
}

export function useTaskDag(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.tasks.dag(cycleId ?? ""),
    queryFn: () => fetchTaskDag(cycleId!),
    enabled: Boolean(cycleId),
  });
}

/** Materialized task DAG, or proposed tasks from the latest task plan when none exist yet. */
export function useTaskDagView(cycleId: string | undefined) {
  const dag = useTaskDag(cycleId);
  const materializedCount = dag.data?.nodes?.length ?? 0;

  const plans = useQuery({
    queryKey: queryKeys.taskPlans.list(cycleId ?? ""),
    queryFn: () => fetchTaskPlans(cycleId!),
    enabled: Boolean(cycleId) && !dag.isLoading && materializedCount === 0,
  });

  const bestPlan = plans.data?.find((p) => p.task_count > 0) ?? plans.data?.[0];

  const planDetail = useQuery({
    queryKey: queryKeys.taskPlans.detail(bestPlan?.id ?? ""),
    queryFn: () => fetchTaskPlan(bestPlan!.id),
    enabled: Boolean(bestPlan?.id) && materializedCount === 0,
  });

  const previewDag = useMemo(() => {
    if (materializedCount > 0 || !planDetail.data?.body) return null;
    return taskPlanBodyToDag(planDetail.data.body as TaskPlanBody);
  }, [materializedCount, planDetail.data]);

  const nodes =
    materializedCount > 0 ? (dag.data?.nodes ?? []) : (previewDag?.nodes ?? []);
  const edges =
    materializedCount > 0 ? (dag.data?.edges ?? []) : (previewDag?.edges ?? []);

  return {
    nodes,
    edges,
    isPreview: materializedCount === 0 && nodes.length > 0,
    planStatus: planDetail.data?.status ?? bestPlan?.status,
    isLoading:
      dag.isLoading || (materializedCount === 0 && (plans.isLoading || planDetail.isLoading)),
    isError: dag.isError,
    error: dag.error,
  };
}

export function useTaskContract(taskId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.taskContract(taskId ?? ""),
    queryFn: () => fetchTaskContract(taskId!),
    enabled: Boolean(taskId),
  });
}

export function useTaskEligibility(taskId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.taskEligibility(taskId ?? ""),
    queryFn: () => fetchTaskEligibility(taskId!),
    enabled: Boolean(taskId),
  });
}

export function useExecutionDetail(executionId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.execution(executionId ?? ""),
    queryFn: () => fetchExecution(executionId!),
    enabled: Boolean(executionId),
  });
}

export function useExecutionEvents(executionId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.executionEvents(executionId ?? ""),
    queryFn: () => fetchExecutionEvents(executionId!),
    enabled: Boolean(executionId),
  });
}

export function useAgentActivity(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.agentActivity(projectId ?? ""),
    queryFn: () => fetchAgentActivity(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useIcAssurance(icId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.icAssurance(icId ?? ""),
    queryFn: () => fetchIcAssurance(icId!),
    enabled: Boolean(icId),
  });
}

export function useLatestImpact(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.impactLatest(cycleId ?? ""),
    queryFn: () => fetchLatestImpactAssessment(cycleId!),
    enabled: Boolean(cycleId),
    retry: (count, err) => !(isApiError(err) && err.status === 404) && count < 2,
  });
}

export function useReleaseEligibility(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.releaseEligibility(cycleId ?? ""),
    queryFn: () => fetchReleaseEligibility(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useCycleOutcome(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.outcome(cycleId ?? ""),
    queryFn: () => fetchCycleOutcome(cycleId!),
    enabled: Boolean(cycleId),
    retry: (count, err) => !(isApiError(err) && err.status === 404) && count < 2,
  });
}

export function useProjectReleases(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.releases(projectId ?? ""),
    queryFn: () => fetchProjectReleases(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useProjectFeatures(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.features(projectId ?? ""),
    queryFn: () => fetchProjectFeatures(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useCycleKnowledge(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.knowledge(cycleId ?? ""),
    queryFn: () => fetchCycleKnowledge(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useFeatureLineage(featureId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.lineage(featureId ?? ""),
    queryFn: () => fetchFeatureLineage(featureId!),
    enabled: Boolean(featureId),
  });
}

export function useConnectors() {
  return useQuery({ queryKey: queryKeys.connectors, queryFn: fetchConnectors });
}

export function useCodeEntities(indexVersionId: string | undefined, qText = "") {
  return useQuery({
    queryKey: queryKeys.codeEntities(indexVersionId ?? "", qText),
    queryFn: () => fetchCodeEntities(indexVersionId!, qText),
    enabled: Boolean(indexVersionId),
  });
}

export function useAuditVerify(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.auditVerify(projectId ?? ""),
    queryFn: () => fetchAuditVerify(projectId),
    enabled: Boolean(projectId),
  });
}

export function useAuditTarget(targetType: string, targetId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.auditTarget(targetType, targetId ?? ""),
    queryFn: () => fetchAuditForTarget(targetType, targetId!),
    enabled: Boolean(targetId),
  });
}

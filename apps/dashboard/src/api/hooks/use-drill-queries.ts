"use client";

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
} from "@/src/api/resources";
import { useQuery } from "@tanstack/react-query";

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

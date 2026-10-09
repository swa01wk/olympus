"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import {
  fetchOrchestratorSession,
  fetchReleaseEligibility,
  fetchTaskDag,
  getApproval,
  getArchitecture,
  getProjectArchitecture,
  getRelease,
  getReleaseManifest,
  getNextTransitions,
  getSourceContent,
  listCapabilities,
  listClarifications,
  listDecompositions,
  getFeatureSpec,
  listFeatureSpecs,
  listFeatures,
  listApprovals,
  listImplementationSpecs,
  listSources,
  listTaskPlans,
} from "@/src/api/resources";

export function useNextTransitions(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.cycles.transitions(cycleId ?? ""),
    queryFn: () => getNextTransitions(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useSources(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.sources.list(projectId ?? ""),
    queryFn: () => listSources(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useSourceContent(projectId: string | undefined, sourceId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.sources.content(projectId ?? "", sourceId ?? ""),
    queryFn: () => getSourceContent(projectId!, sourceId!),
    enabled: Boolean(projectId && sourceId),
  });
}

export function useCapabilities(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.capabilities(projectId ?? ""),
    queryFn: () => listCapabilities(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useFeatures(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.features(projectId ?? ""),
    queryFn: () => listFeatures(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useFeatureSpecs(featureId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.featureSpecs(featureId ?? ""),
    queryFn: () => listFeatureSpecs(featureId!),
    enabled: Boolean(featureId),
  });
}

export function useFeatureSpecDetail(specId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.featureSpecDetail(specId ?? ""),
    queryFn: () => getFeatureSpec(specId!),
    enabled: Boolean(specId),
  });
}

export function useAllFeatureSpecSummaries(featureIds: string[]) {
  return useQueries({
    queries: featureIds.map((featureId) => ({
      queryKey: queryKeys.featureSpecs(featureId),
      queryFn: () => listFeatureSpecs(featureId),
      enabled: Boolean(featureId),
    })),
  });
}

export function useDecompositions(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.decompositions(cycleId ?? ""),
    queryFn: () => listDecompositions(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useClarifications(projectId: string | undefined, status?: string) {
  return useQuery({
    queryKey: queryKeys.clarifications(projectId ?? "", status ?? null),
    queryFn: () => listClarifications(projectId!, status),
    enabled: Boolean(projectId),
  });
}

export function useProjectArchitecture(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.architecture(projectId ?? ""),
    queryFn: () => getProjectArchitecture(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useArchitectureDetail(architectureId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.architectureDetail(architectureId ?? ""),
    queryFn: () => getArchitecture(architectureId!),
    enabled: Boolean(architectureId),
  });
}

export function useApprovals(status?: string) {
  return useQuery({
    queryKey: queryKeys.approvals.list(status),
    queryFn: () => listApprovals(status ? { status } : undefined),
  });
}

export function useImplementationSpecs(featureSpecId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.implementationSpecs(featureSpecId ?? ""),
    queryFn: () => listImplementationSpecs(featureSpecId!),
    enabled: Boolean(featureSpecId),
  });
}

export function useApprovalDetail(approvalId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.approvals.detail(approvalId ?? ""),
    queryFn: () => getApproval(approvalId!),
    enabled: Boolean(approvalId),
  });
}

export function useReleaseDetail(releaseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.release.detail(releaseId ?? ""),
    queryFn: () => getRelease(releaseId!),
    enabled: Boolean(releaseId),
  });
}

export function useReleaseManifest(releaseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.release.manifest(releaseId ?? ""),
    queryFn: () => getReleaseManifest(releaseId!),
    enabled: Boolean(releaseId),
  });
}

export function useOrchestratorSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.orchestrator.session(sessionId ?? ""),
    queryFn: () => fetchOrchestratorSession(sessionId!),
    enabled: Boolean(sessionId),
  });
}

export function useTaskPlans(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.taskPlans.list(cycleId ?? ""),
    queryFn: () => listTaskPlans(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useTaskDag(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.tasks.dag(cycleId ?? ""),
    queryFn: () => fetchTaskDag(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useReleaseEligibility(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.releaseEligibility(cycleId ?? ""),
    queryFn: () => fetchReleaseEligibility(cycleId!),
    enabled: Boolean(cycleId),
  });
}

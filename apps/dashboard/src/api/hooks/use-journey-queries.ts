"use client";

import { queryKeys } from "@/src/api/query-keys";
import {
  getBrownfieldDiscovery,
  getChangeInterpretation,
  getCurrentPolicy,
  getCycleSpecDelta,
  getDefect,
  getDefectRootCause,
  getExpectedBehaviorReview,
  listProjectBaselines,
  getReadinessAssessment,
  getRecoveryProposals,
  getRepository,
  getReviewQueue,
  listChangeRequests,
  listDefectReproductions,
  listDefects,
  listFindings,
  listMaterializations,
  listObservedBehaviors,
  listProjectRepositories,
} from "@/src/api/resources";
import type { RepositoryStatus } from "@/src/api/types/repository";
import { useQuery } from "@tanstack/react-query";

function repositoryPollMs(status: RepositoryStatus | undefined): number | false {
  if (!status) return false;
  if (status === "READY" || status === "ERROR") return false;
  return 3000;
}

export function useChangeRequests(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.changeRequests(projectId ?? ""),
    queryFn: () => listChangeRequests(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useChangeInterpretation(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.changeInterpretation(cycleId ?? ""),
    queryFn: () => getChangeInterpretation(cycleId!),
    enabled: Boolean(cycleId),
    retry: false,
  });
}

export function useCycleSpecDelta(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.cycleSpecDelta(cycleId ?? ""),
    queryFn: () => getCycleSpecDelta(cycleId!),
    enabled: Boolean(cycleId),
    retry: false,
  });
}

export function useDefects(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.defects(projectId ?? ""),
    queryFn: () => listDefects(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useDefectDetail(defectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.defect(defectId ?? ""),
    queryFn: () => getDefect(defectId!),
    enabled: Boolean(defectId),
  });
}

export function useDefectReproductions(defectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.defectReproductions(defectId ?? ""),
    queryFn: () => listDefectReproductions(defectId!),
    enabled: Boolean(defectId),
  });
}

export function useDefectRootCause(defectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.defectRootCause(defectId ?? ""),
    queryFn: () => getDefectRootCause(defectId!),
    enabled: Boolean(defectId),
    retry: false,
  });
}

export function useExpectedBehaviorReview(resolutionId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.expectedBehaviorReview(resolutionId ?? ""),
    queryFn: () => getExpectedBehaviorReview(resolutionId!),
    enabled: Boolean(resolutionId),
    retry: false,
  });
}

export function useProjectBaselines(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.baselines(projectId ?? ""),
    queryFn: () => listProjectBaselines(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useCurrentPolicy() {
  return useQuery({
    queryKey: queryKeys.policyCurrent,
    queryFn: getCurrentPolicy,
  });
}

export function useBrownfieldDiscovery(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.discovery(cycleId ?? ""),
    queryFn: () => getBrownfieldDiscovery(cycleId!),
    enabled: Boolean(cycleId),
    retry: false,
  });
}

export function useObservedBehaviors(cycleId: string | undefined, kind?: string) {
  return useQuery({
    queryKey: [...queryKeys.journey.observedBehaviors(cycleId ?? ""), kind ?? null],
    queryFn: () => listObservedBehaviors(cycleId!, kind),
    enabled: Boolean(cycleId),
  });
}

export function useRecoveryProposals(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.recovery(cycleId ?? ""),
    queryFn: () => getRecoveryProposals(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useReviewQueue(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.reviewQueue(cycleId ?? ""),
    queryFn: () => getReviewQueue(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useReadinessAssessment(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.readiness(cycleId ?? ""),
    queryFn: () => getReadinessAssessment(cycleId!),
    enabled: Boolean(cycleId),
  });
}

export function useProjectRepositories(
  projectId: string | undefined,
  opts?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: queryKeys.repositories.list(projectId ?? ""),
    queryFn: () => listProjectRepositories(projectId!),
    enabled: Boolean(projectId) && (opts?.enabled ?? true),
  });
}

export function useRepository(
  repositoryId: string | undefined,
  opts?: { poll?: boolean; enabled?: boolean },
) {
  const poll = opts?.poll ?? true;
  return useQuery({
    queryKey: queryKeys.repositories.detail(repositoryId ?? ""),
    queryFn: () => getRepository(repositoryId!),
    enabled: Boolean(repositoryId) && (opts?.enabled ?? true),
    refetchInterval: (q) =>
      poll && repositoryId && q.state.data?.status
        ? repositoryPollMs(q.state.data.status)
        : false,
  });
}

export function useRepositoryMaterializations(repositoryId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.repositories.materializations(repositoryId ?? ""),
    queryFn: () => listMaterializations(repositoryId!),
    enabled: Boolean(repositoryId),
  });
}

export function useCycleFindings(cycleId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.journey.findings(cycleId ?? ""),
    queryFn: () => listFindings(cycleId!),
    enabled: Boolean(cycleId),
  });
}

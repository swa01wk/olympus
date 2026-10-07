"use client";

import { queryKeys } from "@/src/api/query-keys";
import {
  getBrownfieldDiscovery,
  getChangeInterpretation,
  getCycleSpecDelta,
  getDefect,
  getDefectRootCause,
  getReadinessAssessment,
  getRecoveryProposals,
  getReviewQueue,
  listChangeRequests,
  listDefectReproductions,
  listDefects,
  listObservedBehaviors,
} from "@/src/api/resources";
import { useQuery } from "@tanstack/react-query";

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

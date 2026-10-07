"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  acceptTaskPlan,
  answerClarification,
  approveRelease,
  createFeatureSpecVersion,
  createRelease,
  decomposeSource,
  deriveSource,
  executeRelease,
  generateImplementationSpecs,
  generateTaskPlan,
  proposeArchitecture,
  requestApproval,
  requestArchitectureApproval,
  requestImplementationSpecApproval,
  requestScopeApproval,
  uploadProductSource,
  type UploadProductSourceInput,
} from "@/src/api/commands";
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import { queryKeys } from "@/src/api/query-keys";
import type { FeatureSpecBody } from "@/src/api/types/product-model";

type StudioScope = {
  projectId: string;
  cycleId: string;
  featureIds?: string[];
  featureSpecIds?: string[];
};

function useStudioInvalidation(scope: StudioScope) {
  const queryClient = useQueryClient();
  return () => invalidateStudioCycle(queryClient, scope);
}

export function useUploadProductSource(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (input: UploadProductSourceInput) =>
      uploadProductSource(scope.projectId, scope.cycleId, input),
    onSettled: invalidate,
  });
}

export function useDecomposeSource(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (sourceId: string) => decomposeSource(sourceId, scope.cycleId),
    onSettled: invalidate,
  });
}

export function useDeriveSource(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (sourceId: string) => deriveSource(sourceId, scope.cycleId),
    onSettled: invalidate,
  });
}

export function useCreateFeatureSpecVersion(scope: StudioScope, featureId: string) {
  const queryClient = useQueryClient();
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (body: FeatureSpecBody) => createFeatureSpecVersion(featureId, body),
    onSettled: () => {
      invalidate();
      void queryClient.invalidateQueries({ queryKey: queryKeys.featureSpecs(featureId) });
    },
  });
}

export function useRequestScopeApproval(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (featureSpecIds: string[]) => requestScopeApproval(scope.cycleId, featureSpecIds),
    onSettled: invalidate,
  });
}

export function useAnswerClarification(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (vars: { clarificationId: string; answer: string }) =>
      answerClarification(vars.clarificationId, vars.answer),
    onSettled: invalidate,
  });
}

export function useProposeArchitecture(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: () => proposeArchitecture(scope.cycleId),
    onSettled: invalidate,
  });
}

export function useRequestArchitectureApproval(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (architectureId: string) =>
      requestArchitectureApproval(architectureId, scope.cycleId),
    onSettled: invalidate,
  });
}

export function useGenerateImplementationSpecs(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: () => generateImplementationSpecs(scope.cycleId),
    onSettled: invalidate,
  });
}

export function useRequestImplementationSpecApproval(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (specId: string) => requestImplementationSpecApproval(specId, scope.cycleId),
    onSettled: invalidate,
  });
}

export function useGenerateTaskPlan(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: () => generateTaskPlan(scope.cycleId),
    onSettled: invalidate,
  });
}

export function useAcceptTaskPlan(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (planId: string) => acceptTaskPlan(planId),
    onSettled: invalidate,
  });
}

export function useRequestApprovalMutation(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (body: Parameters<typeof requestApproval>[1]) =>
      requestApproval(scope.cycleId, body),
    onSettled: invalidate,
  });
}

export function useCreateRelease(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: () => createRelease(scope.cycleId),
    onSettled: invalidate,
  });
}

export function useApproveRelease(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (releaseId: string) => approveRelease(releaseId),
    onSettled: invalidate,
  });
}

export function useExecuteRelease(scope: StudioScope) {
  const invalidate = useStudioInvalidation(scope);
  return useMutation({
    mutationFn: (releaseId: string) => executeRelease(releaseId),
    onSettled: invalidate,
  });
}

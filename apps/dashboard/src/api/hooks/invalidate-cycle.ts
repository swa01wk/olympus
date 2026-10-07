import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";

export function invalidateCycleQueries(
  queryClient: QueryClient,
  cycleId: string,
  taskIds: string[] = [],
) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.detail(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.controlPlane(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.overview(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.cycles.transitions(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.tasks.byCycle(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.integration.candidates(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.inboxRoot });
  for (const tid of taskIds) {
    void queryClient.invalidateQueries({ queryKey: queryKeys.executions.byTask(tid) });
  }
}

export function invalidateStudioCycle(
  queryClient: QueryClient,
  scope: {
    projectId: string;
    cycleId: string;
    featureIds?: string[];
    featureSpecIds?: string[];
  },
) {
  invalidateCycleQueries(queryClient, scope.cycleId);
  void queryClient.invalidateQueries({ queryKey: queryKeys.sources.list(scope.projectId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.decompositions(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.capabilities(scope.projectId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.features(scope.projectId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.taskPlans.list(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.tasks.dag(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.releaseEligibility(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.clarifications(null) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.architecture(scope.projectId) });
  for (const featureId of scope.featureIds ?? []) {
    void queryClient.invalidateQueries({ queryKey: queryKeys.featureSpecs(featureId) });
  }
  for (const specId of scope.featureSpecIds ?? []) {
    void queryClient.invalidateQueries({ queryKey: queryKeys.implementationSpecs(specId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.featureSpecDetail(specId) });
  }
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.changeRequests(scope.projectId) });
  void queryClient.invalidateQueries({
    queryKey: queryKeys.journey.changeInterpretation(scope.cycleId),
  });
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.cycleSpecDelta(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.defects(scope.projectId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.discovery(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.recovery(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.reviewQueue(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.journey.readiness(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.impactLatest(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.knowledge(scope.cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.repositories.list(scope.projectId) });
  void queryClient.invalidateQueries({ queryKey: ["repositories", "detail"] });
  void queryClient.invalidateQueries({ queryKey: ["repositories", "materializations"] });
}

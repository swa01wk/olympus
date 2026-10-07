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
  void queryClient.invalidateQueries({ queryKey: queryKeys.tasks.byCycle(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.integration.candidates(cycleId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.inbox });
  for (const tid of taskIds) {
    void queryClient.invalidateQueries({ queryKey: queryKeys.executions.byTask(tid) });
  }
}

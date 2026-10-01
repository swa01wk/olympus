import type { QueryClient } from "@tanstack/react-query";
import { qk } from "@/lib/query/keys";

/** Maps domain event types to query invalidations. Never applies payload as state. */
export function invalidateForEvent(queryClient: QueryClient, eventType: string, cycleId?: string) {
  if (eventType.startsWith("delivery_cycle.") || eventType.startsWith("task.")) {
    if (cycleId) {
      queryClient.invalidateQueries({ queryKey: qk.cycle(cycleId) });
      queryClient.invalidateQueries({ queryKey: qk.cycleTasks(cycleId) });
      queryClient.invalidateQueries({ queryKey: qk.taskDag(cycleId) });
    }
  }
  if (eventType.startsWith("execution.") || eventType.startsWith("action.")) {
    if (cycleId) queryClient.invalidateQueries({ queryKey: qk.cycleExecutions(cycleId) });
  }
  if (eventType.startsWith("gate.") || eventType.startsWith("finding.")) {
    if (cycleId) {
      queryClient.invalidateQueries({ queryKey: qk.findings(cycleId) });
      queryClient.invalidateQueries({ queryKey: qk.releaseEligibility(cycleId) });
    }
  }
  if (eventType.startsWith("approval.")) {
    queryClient.invalidateQueries({ queryKey: qk.inbox() });
    queryClient.invalidateQueries({ queryKey: qk.approvals() });
  }
}

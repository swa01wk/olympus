import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import { queryKeys } from "@/src/api/query-keys";

describe("invalidateStudioCycle", () => {
  it("invalidates cycle, transitions, inbox, and stage lists", () => {
    const queryClient = {
      invalidateQueries: vi.fn(),
    };
    invalidateStudioCycle(queryClient as never, {
      projectId: "proj-1",
      cycleId: "cycle-2",
      featureIds: ["feat-a"],
      featureSpecIds: ["fspec-b"],
    });

    const keys = queryClient.invalidateQueries.mock.calls.map(
      (c) => c[0].queryKey,
    );

    expect(keys).toContainEqual(queryKeys.cycles.transitions("cycle-2"));
    expect(keys).toContainEqual(queryKeys.inboxRoot);
    expect(keys).toContainEqual(queryKeys.sources.list("proj-1"));
    expect(keys).toContainEqual(queryKeys.decompositions("cycle-2"));
    expect(keys).toContainEqual(queryKeys.taskPlans.list("cycle-2"));
    expect(keys).toContainEqual(queryKeys.tasks.dag("cycle-2"));
    expect(keys).toContainEqual(queryKeys.releaseEligibility("cycle-2"));
    expect(keys).toContainEqual(queryKeys.featureSpecs("feat-a"));
    expect(keys).toContainEqual(queryKeys.implementationSpecs("fspec-b"));
  });

  it("refreshes the project's open clarifications", () => {
    const queryClient = new QueryClient();
    const openKey = queryKeys.clarifications("proj-1", "OPEN");
    const otherProjectKey = queryKeys.clarifications("proj-2", "OPEN");
    queryClient.setQueryData(openKey, []);
    queryClient.setQueryData(otherProjectKey, []);

    invalidateStudioCycle(queryClient, { projectId: "proj-1", cycleId: "cycle-2" });

    expect(queryClient.getQueryState(openKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(otherProjectKey)?.isInvalidated).toBe(false);
  });
});

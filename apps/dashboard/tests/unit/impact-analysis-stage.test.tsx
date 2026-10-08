import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ImpactAnalysisStage } from "@/components/studio/workspace/journeys/ImpactAnalysisStage";

vi.mock("@/src/api/commands", () => ({
  runImpactAssessment: vi.fn(),
  proposeArchitectureDelta: vi.fn(),
  declineArchitectureDelta: vi.fn(),
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => ({ data: { roles: ["APPROVER"] } }),
  useDeliveryCycle: () => ({
    data: {
      id: "cyc-fc",
      project_id: "proj-1",
      key: "FC-1",
      type: "FEATURE_CHANGE",
      objective: "Change",
      state: "IMPACT_ANALYSIS",
      state_version: 1,
      repository_id: null,
      base_sha: null,
      allowed_commands: [],
    },
  }),
}));

const useLatestImpact = vi.fn();

vi.mock("@/src/api/hooks/use-drill-queries", () => ({
  useLatestImpact: (...args: unknown[]) => useLatestImpact(...args),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ImpactAnalysisStage", () => {
  it("hides architecture delta panel when not suggested", () => {
    useLatestImpact.mockReturnValue({
      data: { summary: "Low impact", architecture_delta_suggested: false },
      isLoading: false,
      isError: false,
    });
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.queryByText(/Architecture change suggested/i)).toBeNull();
  });

  it("shows architecture delta panel when suggested", () => {
    useLatestImpact.mockReturnValue({
      data: { summary: "High impact", architecture_delta_suggested: true, items_by_type: {} },
      isLoading: false,
      isError: false,
    });
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.getByText(/Architecture change suggested/i)).toBeTruthy();
    expect(screen.getByText(/can't be approved until the backend persists deltas/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Propose a delta" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Decline with note" })).toBeTruthy();
  });
});

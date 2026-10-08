import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntegrationAssuranceStage } from "@/components/studio/workspace/IntegrationAssuranceStage";

vi.mock("@/src/api/commands", () => ({
  waiveFinding: vi.fn(),
  remediateFinding: vi.fn(),
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useIntegrationCandidates: () => ({ data: [] }),
}));

vi.mock("@/src/api/hooks/use-drill-queries", () => ({
  useIcAssurance: () => ({ data: {}, isLoading: false }),
}));

const openBlocker = {
  id: "find-open",
  key: "F-001",
  delivery_cycle_id: "cyc-1",
  category: "TEST_FAILURE",
  severity: "BLOCKER",
  blocking: true,
  title: "Assertion failed in checkout",
  status: "OPEN",
  detail: { code_refs: [{ file_path: "tests/checkout.test.ts", line_start: 42 }] },
};

const waived = {
  ...openBlocker,
  id: "find-waived",
  key: "F-002",
  title: "Waived lint warning",
  status: "WAIVED",
  blocking: false,
  detail: {},
};

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useCycleFindings: () => ({ data: [openBlocker, waived], isLoading: false }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => cleanup());

describe("IntegrationAssuranceStage findings", () => {
  it("shows Waive and Remediate on open BLOCKER finding only", () => {
    wrap(
      <IntegrationAssuranceStage projectId="proj-1" cycleId="cyc-1" stage="ASSURANCE" />,
    );
    expect(screen.getByText(/Blocking — must be resolved/i)).toBeTruthy();
    expect(screen.getByText(/tests\/checkout.test.ts:42/)).toBeTruthy();
    const waiveButtons = screen.getAllByRole("button", { name: "Waive" });
    const remediateButtons = screen.getAllByRole("button", { name: "Remediate" });
    expect(waiveButtons).toHaveLength(1);
    expect(remediateButtons).toHaveLength(1);
  });
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BugFixStage } from "@/components/studio/workspace/journeys/BugFixStage";

const proceedUnreproduced = vi.fn();
const rejectDefect = vi.fn();

vi.mock("@/src/api/commands", () => ({
  proceedUnreproduced: (...args: unknown[]) => proceedUnreproduced(...args),
  rejectDefect: (...args: unknown[]) => rejectDefect(...args),
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => ({ data: { roles: ["OPERATOR", "APPROVER"] } }),
}));

const defectDetail = {
  id: "def-1",
  key: "DEF-1",
  status: "NOT_REPRODUCIBLE",
  title: "Login fails",
  description: "500 on submit",
  triage: { severity: "HIGH" },
  linked_feature_ids: [],
  expected_ac_ids: [],
  affected_sha: null,
  delivery_cycle_id: "cyc-bf",
};

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useDefects: () => ({
    data: [
      {
        id: "def-1",
        key: "DEF-1",
        status: "NOT_REPRODUCIBLE",
        delivery_cycle_id: "cyc-bf",
        title: "Login fails",
        severity: "HIGH",
      },
    ],
    isLoading: false,
  }),
  useDefectDetail: () => ({ data: defectDetail, isLoading: false }),
  useDefectReproductions: () => ({
    data: [{ phase: "PRE_REPAIR", outcome: "NOT_REPRODUCED", commit_sha: "abc123" }],
    isLoading: false,
  }),
  useDefectRootCause: () => ({ data: null, isLoading: false }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BugFixStage defect actions", () => {
  it("shows proceed unreproduced at REPRODUCTION when not reproducible", async () => {
    proceedUnreproduced.mockResolvedValue({ approval_id: "apr-1", status: "APPROVED" });
    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="REPRODUCTION" />);

    fireEvent.change(screen.getByLabelText(/Reason \(required\)/i), {
      target: { value: "Cannot reproduce in staging" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Proceed unreproduced" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    await waitFor(() => expect(proceedUnreproduced).toHaveBeenCalledWith(
      "def-1",
      "Cannot reproduce in staging",
      expect.any(String),
    ));
  });

  it("shows reject with confirmation at TRIAGE", async () => {
    defectDetail.status = "TRIAGED";
    rejectDefect.mockResolvedValue({ id: "def-1", status: "REJECTED" });

    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="TRIAGE" />);

    fireEvent.click(screen.getByRole("button", { name: "Reject defect" }));
    expect(screen.getByText(/Confirm rejection/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm reject" }));

    await waitFor(() =>
      expect(rejectDefect).toHaveBeenCalledWith("def-1", null, expect.any(String)),
    );
  });
});

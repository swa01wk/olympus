import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntegrationAssuranceStage } from "@/components/studio/workspace/IntegrationAssuranceStage";

const waiveFinding = vi.fn();
const remediateFinding = vi.fn();

vi.mock("@/src/api/commands", () => ({
  waiveFinding: (...args: unknown[]) => waiveFinding(...args),
  remediateFinding: (...args: unknown[]) => remediateFinding(...args),
}));

const pendingWaiverInbox = [
  {
    kind: "APPROVAL",
    id: "apr-waiver",
    title: "FINDING_WAIVER APR-9",
    delivery_cycle_id: "cyc-1",
    approval: {
      id: "apr-waiver",
      key: "APR-9",
      approval_type: "FINDING_WAIVER",
      subject_type: "FINDING",
      subject_id: "find-pending",
      subject_hash: "fp",
      status: "PENDING",
    },
  },
];

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useIntegrationCandidates: () => ({ data: [] }),
  useInbox: () => ({ data: pendingWaiverInbox, isLoading: false }),
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

const openNonBlocking = {
  ...openBlocker,
  id: "find-minor",
  key: "F-003",
  severity: "MINOR",
  category: "STYLE",
  title: "Long function",
  blocking: false,
  detail: {},
};

const openPendingWaiver = {
  ...openBlocker,
  id: "find-pending",
  key: "F-004",
  title: "Flaky integration test",
  detail: {},
};

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useCycleFindings: () => ({
    data: [openBlocker, waived, openNonBlocking, openPendingWaiver],
    isLoading: false,
  }),
  useProjectBaselines: () => ({ data: [], isLoading: false }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function row(key: string) {
  const li = screen.getByText(key).closest("li");
  if (!li) throw new Error(`row ${key} not found`);
  return within(li);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("IntegrationAssuranceStage findings", () => {
  it("shows Waive and Remediate on an open BLOCKER finding and neither on a waived one", () => {
    wrap(<IntegrationAssuranceStage projectId="proj-1" cycleId="cyc-1" stage="ASSURANCE" />);
    expect(screen.getAllByText(/Blocking — must be resolved/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/tests\/checkout.test.ts:42/)).toBeTruthy();
    expect(row("F-001").getByRole("button", { name: "Waive" })).toBeTruthy();
    expect(row("F-001").getByRole("button", { name: "Remediate" })).toBeTruthy();
    expect(row("F-002").queryByRole("button", { name: "Waive" })).toBeNull();
    expect(row("F-002").queryByRole("button", { name: "Remediate" })).toBeNull();
  });

  it("offers Waive but not Remediate on an open non-blocking finding", () => {
    wrap(<IntegrationAssuranceStage projectId="proj-1" cycleId="cyc-1" stage="ASSURANCE" />);
    expect(row("F-003").getByRole("button", { name: "Waive" })).toBeTruthy();
    expect(row("F-003").queryByRole("button", { name: "Remediate" })).toBeNull();
  });

  it("hides actions and says so when a waiver is already pending", () => {
    wrap(<IntegrationAssuranceStage projectId="proj-1" cycleId="cyc-1" stage="ASSURANCE" />);
    expect(row("F-004").getByText("Waiver pending approval")).toBeTruthy();
    expect(row("F-004").queryByRole("button", { name: "Waive" })).toBeNull();
    expect(row("F-004").queryByRole("button", { name: "Remediate" })).toBeNull();
  });

  it("previews and sends the waive call for the finding", async () => {
    waiveFinding.mockResolvedValue({ approval_id: "apr-1" });
    wrap(<IntegrationAssuranceStage projectId="proj-1" cycleId="cyc-1" stage="ASSURANCE" />);
    const r = row("F-001");
    fireEvent.click(r.getByRole("button", { name: "Waive" }));
    expect(r.getByText(/POST \S*\/findings\/find-open\/waive/)).toBeTruthy();
    fireEvent.click(r.getByRole("button", { name: "Confirm send" }));
    await waitFor(() =>
      expect(waiveFinding).toHaveBeenCalledWith("find-open", expect.any(String)),
    );
    expect(remediateFinding).not.toHaveBeenCalled();
  });

  it("previews and sends the remediate call for the finding", async () => {
    remediateFinding.mockResolvedValue({ task_id: "task-1" });
    wrap(<IntegrationAssuranceStage projectId="proj-1" cycleId="cyc-1" stage="ASSURANCE" />);
    const r = row("F-001");
    fireEvent.click(r.getByRole("button", { name: "Remediate" }));
    expect(r.getByText(/POST \S*\/findings\/find-open\/remediate/)).toBeTruthy();
    fireEvent.click(r.getByRole("button", { name: "Confirm send" }));
    await waitFor(() =>
      expect(remediateFinding).toHaveBeenCalledWith("find-open", expect.any(String)),
    );
    expect(waiveFinding).not.toHaveBeenCalled();
  });
});

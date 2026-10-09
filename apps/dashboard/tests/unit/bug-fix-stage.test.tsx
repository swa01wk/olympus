import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

function makeDefectDetail(status: string) {
  return {
    id: "def-1",
    key: "DEF-1",
    status,
    title: "Login fails",
    description: "500 on submit",
    triage: { severity: "HIGH" },
    linked_feature_ids: [],
    expected_ac_ids: [],
    affected_sha: null,
    delivery_cycle_id: "cyc-bf",
  };
}

function makePolicy(allowUnreproduced: boolean) {
  return {
    id: "pol-1",
    name: "default",
    version: 1,
    content_hash: "h",
    content: { bugfix: { reproduction_attempts: 3, allow_unreproduced: allowUnreproduced } },
  };
}

const fixtures = vi.hoisted(() => ({
  detail: null as Record<string, unknown> | null,
  policy: null as Record<string, unknown> | null,
}));

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useDefects: () => ({
    data: [
      {
        id: "def-1",
        key: "DEF-1",
        status: fixtures.detail?.status,
        delivery_cycle_id: "cyc-bf",
        title: "Login fails",
        severity: "HIGH",
      },
    ],
    isLoading: false,
  }),
  useDefectDetail: () => ({ data: fixtures.detail, isLoading: false }),
  useDefectReproductions: () => ({
    data: [{ phase: "PRE_REPAIR", outcome: "NOT_REPRODUCED", commit_sha: "abc123" }],
    isLoading: false,
  }),
  useDefectRootCause: () => ({ data: null, isLoading: false }),
  useCurrentPolicy: () => ({ data: fixtures.policy, isLoading: false }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  fixtures.detail = makeDefectDetail("NOT_REPRODUCIBLE");
  fixtures.policy = makePolicy(true);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BugFixStage defect actions", () => {
  it("proceeds unreproduced at REPRODUCTION when not reproducible and policy allows", async () => {
    proceedUnreproduced.mockResolvedValue({ approval_id: "apr-1", status: "APPROVED" });
    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="REPRODUCTION" />);

    fireEvent.change(screen.getByLabelText(/Reason \(required\)/i), {
      target: { value: "Cannot reproduce in staging" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Proceed unreproduced" }));
    expect(screen.getByText(/POST \/defects\/def-1\/proceed-unreproduced/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    await waitFor(() =>
      expect(proceedUnreproduced).toHaveBeenCalledWith(
        "def-1",
        "Cannot reproduce in staging",
        expect.any(String),
      ),
    );
    expect(
      await screen.findByText("Proceeding without reproduction (approval recorded)."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Proceed unreproduced" })).toBeNull();
  });

  it("disables proceed unreproduced when policy bugfix.allow_unreproduced is off", () => {
    fixtures.policy = makePolicy(false);
    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="REPRODUCTION" />);

    expect(
      screen.getByText(
        "Policy bugfix.allow_unreproduced is off, so this defect can't proceed without a reproduction.",
      ),
    ).toBeTruthy();
    expect((screen.getByLabelText(/Reason \(required\)/i) as HTMLTextAreaElement).disabled).toBe(
      true,
    );
    expect(
      (screen.getByRole("button", { name: "Proceed unreproduced" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("does not offer proceed unreproduced unless the defect is NOT_REPRODUCIBLE", () => {
    fixtures.detail = makeDefectDetail("TRIAGED");
    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="REPRODUCTION" />);
    expect(screen.queryByRole("button", { name: "Proceed unreproduced" })).toBeNull();
  });

  it("shows reject with confirmation at TRIAGE", async () => {
    fixtures.detail = makeDefectDetail("TRIAGED");
    rejectDefect.mockResolvedValue({ id: "def-1", status: "REJECTED" });

    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="TRIAGE" />);

    fireEvent.click(screen.getByRole("button", { name: "Reject defect" }));
    expect(screen.getByText(/Confirm rejection/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm reject" }));

    await waitFor(() =>
      expect(rejectDefect).toHaveBeenCalledWith("def-1", null, expect.any(String)),
    );
  });

  it.each(["REJECTED", "FIXED", "RELEASED"])("does not offer reject for %s defects", (status) => {
    fixtures.detail = makeDefectDetail(status);
    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="REGRESSION" />);
    expect(screen.queryByRole("button", { name: "Reject defect" })).toBeNull();
  });
});

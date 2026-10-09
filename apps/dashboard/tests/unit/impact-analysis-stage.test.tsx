import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ImpactAnalysisStage } from "@/components/studio/workspace/journeys/ImpactAnalysisStage";
import { queryKeys } from "@/src/api/query-keys";

const runImpactAssessment = vi.fn();
const proposeArchitectureDelta = vi.fn();
const declineArchitectureDelta = vi.fn();

vi.mock("@/src/api/commands", () => ({
  runImpactAssessment: (...args: unknown[]) => runImpactAssessment(...args),
  proposeArchitectureDelta: (...args: unknown[]) => proposeArchitectureDelta(...args),
  declineArchitectureDelta: (...args: unknown[]) => declineArchitectureDelta(...args),
}));

const state = vi.hoisted(() => ({
  roles: ["APPROVER"] as string[],
  inbox: [] as Record<string, unknown>[],
  approved: [] as Record<string, unknown>[],
  latestArchitecture: null as Record<string, unknown> | null,
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => ({ data: { roles: state.roles } }),
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
  useInbox: () => ({ data: state.inbox, isLoading: false }),
}));

vi.mock("@/src/api/hooks/use-studio-queries", () => ({
  useApprovals: () => ({ data: state.approved, isLoading: false }),
  useProjectArchitecture: () => ({ data: state.latestArchitecture, isLoading: false }),
  useArchitectureDetail: () => ({ data: undefined, isLoading: false }),
}));

const useLatestImpact = vi.fn();

vi.mock("@/src/api/hooks/use-drill-queries", () => ({
  useLatestImpact: (...args: unknown[]) => useLatestImpact(...args),
}));

function suggested(status = "COMPLETE") {
  useLatestImpact.mockReturnValue({
    data: {
      id: "ia-1",
      status,
      summary: "High impact",
      architecture_delta_suggested: true,
      items_by_type: {},
    },
    isLoading: false,
    isError: false,
  });
}

function wrap(ui: React.ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const deltaArchitecture = {
  id: "arch-d",
  version: 3,
  status: "PROPOSED",
  kind: "DELTA",
  body: {
    rationale: "Split billing out of orders",
    added_components: [{ name: "billing" }, { name: "invoices" }],
    changed_components: [{ name: "orders" }],
    changed_contracts: [{ key: "POST /invoices" }],
  },
  contracts: [],
};

beforeEach(() => {
  state.roles = ["APPROVER"];
  state.inbox = [];
  state.approved = [];
  state.latestArchitecture = { ...deltaArchitecture, id: "arch-base", version: 2, status: "APPROVED", kind: "FULL", body: {} };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ImpactAnalysisStage", () => {
  it("hides architecture delta panel when not suggested", () => {
    useLatestImpact.mockReturnValue({
      data: { status: "COMPLETE", summary: "Low impact", architecture_delta_suggested: false },
      isLoading: false,
      isError: false,
    });
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.queryByText(/Architecture change suggested/i)).toBeNull();
  });

  it("hides architecture delta panel when the latest assessment is not COMPLETE", () => {
    suggested("RUNNING");
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.queryByText(/Architecture change suggested/i)).toBeNull();
  });

  it("offers Propose and Decline when suggested and nothing is pending or resolved", () => {
    suggested();
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.getByText(/Architecture change suggested/i)).toBeTruthy();
    expect(screen.queryByText(/can't be approved until the backend persists deltas/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Propose a delta" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Decline with note" })).toBeTruthy();
  });

  it("shows the pending delta summary and hides actions", () => {
    suggested();
    state.latestArchitecture = deltaArchitecture;
    state.inbox = [
      {
        kind: "APPROVAL",
        id: "apr-ad",
        title: "ARCHITECTURE_DELTA APR-3",
        delivery_cycle_id: "cyc-fc",
        approval: {
          id: "apr-ad",
          key: "APR-3",
          approval_type: "ARCHITECTURE_DELTA",
          subject_type: "architecture",
          subject_id: "arch-d",
          subject_hash: "h",
          status: "PENDING",
        },
      },
    ];
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(
      screen.getByText("Delta v3 proposed, awaiting approval in the Decision panel"),
    ).toBeTruthy();
    expect(screen.getByText("Split billing out of orders")).toBeTruthy();
    expect(
      screen.getByText(/2 added components · 1 changed components · 1 changed contracts/),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Propose a delta" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Decline with note" })).toBeNull();
  });

  it("treats a proposed DELTA architecture as pending without an inbox row", () => {
    suggested();
    state.latestArchitecture = deltaArchitecture;
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.getByText(/Delta v3 proposed/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Propose a delta" })).toBeNull();
  });

  it("shows resolved (declined) and hides actions", () => {
    suggested();
    state.approved = [
      {
        id: "apr-dec",
        approval_type: "ARCHITECTURE_DELTA",
        subject_type: "ARCHITECTURE_DELTA_DECLINED",
        subject_id: "cyc-fc",
        status: "APPROVED",
        delivery_cycle_id: "cyc-fc",
      },
    ];
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.getByText("Architecture delta resolved (declined)")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Propose a delta" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Decline with note" })).toBeNull();
  });

  it("shows resolved (approved) for an approved delta approval on this cycle only", () => {
    suggested();
    state.approved = [
      {
        id: "apr-other",
        approval_type: "ARCHITECTURE_DELTA",
        subject_type: "architecture",
        status: "APPROVED",
        delivery_cycle_id: "cyc-other",
      },
      {
        id: "apr-ad",
        approval_type: "ARCHITECTURE_DELTA",
        subject_type: "architecture",
        status: "APPROVED",
        delivery_cycle_id: "cyc-fc",
      },
    ];
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.getByText("Architecture delta resolved (approved)")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Propose a delta" })).toBeNull();
  });

  it("shows Decline read-only with the role message for non-approvers", () => {
    suggested();
    state.roles = ["OPERATOR"];
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    expect(screen.getByText("You need the APPROVER role to do this.")).toBeTruthy();
    expect((screen.getByLabelText(/Note \(required\)/i) as HTMLTextAreaElement).disabled).toBe(true);
    expect(
      (screen.getByRole("button", { name: "Decline with note" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("blocks Decline until a note is entered, then previews and sends it", async () => {
    suggested();
    declineArchitectureDelta.mockResolvedValue({ approval_id: "apr-dec" });
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    const decline = screen.getByRole("button", { name: "Decline with note" }) as HTMLButtonElement;
    expect(decline.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Note \(required\)/i), {
      target: { value: "No structural change" },
    });
    expect(decline.disabled).toBe(false);
    fireEvent.click(decline);
    expect(
      screen.getByText(/POST \/delivery-cycles\/cyc-fc\/architecture-delta\/decline/),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));
    await waitFor(() =>
      expect(declineArchitectureDelta).toHaveBeenCalledWith(
        "cyc-fc",
        "No structural change",
        expect.any(String),
      ),
    );
  });

  it("stops offering Propose once a propose task is scheduled", async () => {
    suggested();
    proposeArchitectureDelta.mockResolvedValue({ architecture_delta_task_id: "task-ad" });
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />);
    fireEvent.click(screen.getByRole("button", { name: "Propose a delta" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));
    await waitFor(() => expect(screen.getByText(/Atlas is proposing a delta \(task task-ad\)/)).toBeTruthy());
    expect(proposeArchitectureDelta).toHaveBeenCalledWith("cyc-fc", expect.any(String));
    expect(screen.queryByRole("button", { name: "Propose a delta" })).toBeNull();
  });

  it("invalidates the latest impact query after running an assessment", async () => {
    useLatestImpact.mockReturnValue({ data: undefined, isLoading: false, isError: false });
    runImpactAssessment.mockResolvedValue({ id: "ia-2", status: "COMPLETE" });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(client, "invalidateQueries");
    wrap(<ImpactAnalysisStage cycleId="cyc-fc" />, client);
    fireEvent.click(screen.getByRole("button", { name: "Run impact assessment" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.impactLatest("cyc-fc") }),
    );
  });
});

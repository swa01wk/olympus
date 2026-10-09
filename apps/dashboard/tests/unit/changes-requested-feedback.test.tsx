import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChangesRequestedFeedback } from "@/components/studio/ChangesRequestedFeedback";
import { listApprovals } from "@/src/api/resources";
import type { ApprovalView } from "@/src/api/types/core";

vi.mock("@/src/api/resources", () => ({
  listApprovals: vi.fn(),
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => ({
    data: { actor_id: "actor-me", kind: "HUMAN", name: "Dana Reviewer", roles: ["APPROVER"] },
  }),
}));

const changesRequested: ApprovalView = {
  id: "apr-cr",
  key: "APR-9",
  approval_type: "SCOPE",
  subject_type: "scope_set",
  subject_id: "scope-1",
  subject_version: 1,
  subject_hash: "hash",
  status: "CHANGES_REQUESTED",
  project_id: "proj-1",
  delivery_cycle_id: "cyc-gf",
  created_at: "2026-10-08T11:00:00Z",
  decided_by_actor_id: "actor-42",
  decided_at: "2026-10-08T11:30:00Z",
  decision_note: "Tighten scope wording",
};

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function renderFeedback() {
  return wrap(
    <ChangesRequestedFeedback cycleId="cyc-gf" cycleType="GREENFIELD_BUILD" stage="PRODUCT_MODEL" />,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ChangesRequestedFeedback", () => {
  it("shows the decision note, author and time from the approval", async () => {
    vi.mocked(listApprovals).mockResolvedValue([changesRequested]);
    renderFeedback();
    expect(await screen.findByText(/Changes requested/i)).toBeTruthy();
    expect(screen.getByText("Tighten scope wording")).toBeTruthy();
    expect(screen.getByText(/2026-10-08T11:30:00Z/)).toBeTruthy();
    expect(screen.getByText("actor-42")).toBeTruthy();
    expect(listApprovals).toHaveBeenCalledWith();
  });

  it("shows the current actor's name when they requested the changes", async () => {
    vi.mocked(listApprovals).mockResolvedValue([
      { ...changesRequested, decided_by_actor_id: "actor-me" },
    ]);
    renderFeedback();
    expect(await screen.findByText(/by Dana Reviewer/)).toBeTruthy();
  });

  it("hides once a newer approval exists for the stage", async () => {
    vi.mocked(listApprovals).mockResolvedValue([
      changesRequested,
      {
        ...changesRequested,
        id: "apr-rev",
        key: "APR-10",
        status: "PENDING",
        created_at: "2026-10-08T12:00:00Z",
        decided_by_actor_id: null,
        decided_at: null,
        decision_note: null,
      },
    ]);
    const { container } = renderFeedback();
    await waitFor(() => expect(listApprovals).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe("");
  });
});

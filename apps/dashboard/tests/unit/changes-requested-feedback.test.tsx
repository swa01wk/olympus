import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChangesRequestedFeedback } from "@/components/studio/ChangesRequestedFeedback";

vi.mock("@/src/api/resources", () => ({
  listApprovals: vi.fn().mockResolvedValue([
    {
      id: "apr-cr",
      key: "APR-9",
      approval_type: "SCOPE",
      subject_type: "ScopeBundle",
      subject_id: "scope-1",
      subject_version: 1,
      subject_hash: "hash",
      status: "CHANGES_REQUESTED",
      project_id: "proj-1",
      delivery_cycle_id: "cyc-gf",
    },
  ]),
  fetchAuditForTarget: vi.fn().mockResolvedValue([
    {
      id: "aud-1",
      action: "transition.accepted",
      actor_id: "actor-42",
      before: { status: "PENDING" },
      after: { status: "CHANGES_REQUESTED", note: "Tighten scope wording" },
      occurred_at: "2026-10-08T11:30:00Z",
    },
  ]),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => cleanup());

describe("ChangesRequestedFeedback", () => {
  it("shows change-request note with audit author and time", async () => {
    wrap(
      <ChangesRequestedFeedback
        cycleId="cyc-gf"
        cycleType="GREENFIELD_BUILD"
        stage="PRODUCT_MODEL"
      />,
    );
    expect(await screen.findByText(/Changes requested/i)).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/Tighten scope wording/)).toBeTruthy());
    expect(screen.getByText(/2026-10-08T11:30:00Z/)).toBeTruthy();
    expect(screen.getByText(/actor-42/)).toBeTruthy();
  });
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BrownfieldBaselineStage } from "@/components/studio/workspace/journeys/BrownfieldBaselineStage";
import { OlympusApiError } from "@/src/api/errors";
import { queryKeys } from "@/src/api/query-keys";
import type { ReviewQueueItem } from "@/src/api/types/journey";

const recordPromotionDecision = vi.fn();

vi.mock("@/src/api/commands", () => ({
  recordPromotionDecision: (...args: unknown[]) => recordPromotionDecision(...args),
}));

let actorState: { data?: { roles: string[] }; isPending?: boolean } = {
  data: { roles: ["OPERATOR"] },
};

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => actorState,
}));

const queueItem: ReviewQueueItem = {
  subject_type: "FEATURE_SPEC",
  subject_id: "spec-rec-1",
  detail: { lineage_key: "auth.login", confidence: 0.82, claimed_confidence: null },
  decided: false,
  decision: null,
};

let queueItems: ReviewQueueItem[] = [queueItem];

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useReviewQueue: () => ({ data: queueItems, isLoading: false }),
  useProjectBaselines: () => ({ data: [], isLoading: false }),
}));

function wrap(ui: React.ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  actorState = { data: { roles: ["OPERATOR"] } };
  queueItems = [queueItem];
});

describe("BrownfieldBaselineStage", () => {
  it("disables approver-only decisions for non-approver with role message", () => {
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    expect(screen.getByText(/You need the APPROVER role to do this/i)).toBeTruthy();
    const promote = screen.getByRole("radio", { name: /PROMOTE AS CANONICAL/i });
    expect(promote).toHaveProperty("disabled", true);
    expect(screen.getByRole("radio", { name: /CONFIRM EXISTING/i })).toHaveProperty(
      "disabled",
      false,
    );
  });

  it("defaults a non-approver FEATURE_SPEC to the first usable decision and keeps the role message", () => {
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    expect(screen.getByRole("radio", { name: /CONFIRM EXISTING/i })).toHaveProperty("checked", true);
    expect(screen.getByRole("radio", { name: /PROMOTE AS CANONICAL/i })).toHaveProperty(
      "checked",
      false,
    );
    expect(screen.getByText(/You need the APPROVER role to do this/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Preview decision" })).toHaveProperty(
      "disabled",
      false,
    );
  });

  it("renders an ARCHITECTURE item disabled with the role message for a non-approver", () => {
    queueItems = [
      {
        subject_type: "ARCHITECTURE",
        subject_id: "arch-rec-1",
        detail: { version: 3 },
        decided: false,
        decision: null,
      },
    ];
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    const approve = screen.getByRole("radio", { name: /APPROVE AS PROJECT ARCHITECTURE/i });
    expect(approve).toHaveProperty("disabled", true);
    expect(approve).toHaveProperty("checked", true);
    expect(screen.getByText(/You need the APPROVER role to do this/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Preview decision" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByText("v3")).toBeTruthy();
  });

  it("hides decision controls while the actor is loading", () => {
    actorState = { isPending: true };
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    expect(screen.queryByText(/You need the APPROVER role/i)).toBeNull();
    expect(screen.queryByRole("radio", { name: /PROMOTE AS CANONICAL/i })).toBeNull();
  });

  it("renders known detail fields with labels and confidence as a percentage", () => {
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    expect(screen.getByText("Lineage")).toBeTruthy();
    expect(screen.getByText("auth.login")).toBeTruthy();
    expect(screen.getByText("Confidence")).toBeTruthy();
    expect(screen.getByText("82%")).toBeTruthy();
    expect(screen.queryByText("Claimed confidence")).toBeNull();
  });

  it("shows the evidence hint under Activate for BASELINE items", () => {
    queueItems = [
      {
        subject_type: "BASELINE",
        subject_id: "bl-1",
        detail: { lineage_key: "auth.login", check_ref: "tests/test_auth.py::test_login", source: "RECOVERED" },
        decided: false,
        decision: null,
      },
    ];
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    expect(screen.getByText("Activation needs passing evidence for this check.")).toBeTruthy();
    expect(screen.getByText("tests/test_auth.py::test_login")).toBeTruthy();
  });

  it("explains that decided items leave the queue", () => {
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);
    expect(
      screen.getByText("Promoted, confirmed, rejected and activated items leave the queue."),
    ).toBeTruthy();
  });

  it("posts promotion decision with exact body", async () => {
    recordPromotionDecision.mockResolvedValue({});
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />);

    fireEvent.click(screen.getByRole("radio", { name: /REJECT AS NOT INTENDED/i }));
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Not part of product intent" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview decision" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    await waitFor(() => expect(recordPromotionDecision).toHaveBeenCalled());
    expect(recordPromotionDecision).toHaveBeenCalledWith(
      "cyc-bf",
      {
        subject_type: "FEATURE_SPEC",
        subject_id: "spec-rec-1",
        decision: "REJECT_AS_NOT_INTENDED",
        note: "Not part of product intent",
      },
      expect.any(String),
    );
  });

  it("invalidates review queue, next transitions and inbox after a decision", async () => {
    recordPromotionDecision.mockResolvedValue({});
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />, client);

    fireEvent.click(screen.getByRole("button", { name: "Preview decision" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    await waitFor(() => expect(recordPromotionDecision).toHaveBeenCalled());
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: queryKeys.journey.reviewQueue("cyc-bf"),
      }),
    );
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.cycles.transitions("cyc-bf") });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.inboxRoot });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sources.list("proj-1") });
  });

  it("refreshes the review queue when the decision fails as already decided", async () => {
    recordPromotionDecision.mockRejectedValue(
      new OlympusApiError(409, "ALREADY_DECIDED", "Already decided"),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, "invalidateQueries");
    wrap(<BrownfieldBaselineStage projectId="proj-1" cycleId="cyc-bf" />, client);

    fireEvent.click(screen.getByRole("button", { name: "Preview decision" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: queryKeys.journey.reviewQueue("cyc-bf"),
    });
  });
});

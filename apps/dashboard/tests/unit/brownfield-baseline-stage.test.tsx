import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BrownfieldBaselineStage } from "@/components/studio/workspace/journeys/BrownfieldBaselineStage";

const recordPromotionDecision = vi.fn();

vi.mock("@/src/api/commands", () => ({
  recordPromotionDecision: (...args: unknown[]) => recordPromotionDecision(...args),
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => ({ data: { roles: ["OPERATOR"] } }),
  useDeliveryCycle: () => ({
    data: {
      id: "cyc-bf",
      project_id: "proj-1",
      key: "BF-1",
      type: "BROWNFIELD_ONBOARDING",
      objective: "Onboard",
      state: "BASELINE",
      state_version: 1,
      repository_id: "repo-1",
      base_sha: null,
      allowed_commands: [],
    },
  }),
}));

const queueItem = {
  subject_type: "FEATURE_SPEC",
  subject_id: "spec-rec-1",
  detail: { lineage_key: "auth.login", confidence: 0.82, citations: ["src/auth.py:10"] },
  decided: false,
  decision: null,
};

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useReviewQueue: () => ({ data: [queueItem], isLoading: false }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BrownfieldBaselineStage", () => {
  it("disables approver-only decisions for non-approver with role message", () => {
    wrap(<BrownfieldBaselineStage cycleId="cyc-bf" />);
    expect(screen.getByText(/You need the APPROVER role to do this/i)).toBeTruthy();
    const promote = screen.getByRole("radio", { name: /PROMOTE AS CANONICAL/i });
    expect(promote).toHaveProperty("disabled", true);
    expect(screen.getByRole("radio", { name: /CONFIRM EXISTING/i })).toHaveProperty(
      "disabled",
      false,
    );
  });

  it("posts promotion decision with exact body", async () => {
    recordPromotionDecision.mockResolvedValue({});
    wrap(<BrownfieldBaselineStage cycleId="cyc-bf" />);

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
});

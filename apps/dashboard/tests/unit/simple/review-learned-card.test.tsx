import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReviewLearnedCard } from "@/components/simple/ReviewLearnedCard";
import type { ReviewItem } from "@/src/api/types/autopilot";

const items: ReviewItem[] = [
  {
    subject_type: "FEATURE_SPEC",
    subject_id: "f1",
    group: "Features",
    title: "Add a note",
    detail: "Rejects empty notes",
    suggestion: "keep",
    why: null,
    keep_label: "Yes, this is a feature",
    drop_label: "No, not a real feature",
  },
  {
    subject_type: "BASELINE",
    subject_id: "b1",
    group: "Current behavior to protect",
    title: "test_add_note",
    detail: null,
    suggestion: "drop",
    why: "No passing test proves this behavior yet.",
    keep_label: "Protect this behavior",
    drop_label: "Don't protect it",
  },
];

const submitReview = vi.fn().mockResolvedValue({});
vi.mock("@/src/api/autopilot", () => ({
  fetchReview: vi.fn(() => Promise.resolve(items)),
  submitReview: (...a: unknown[]) => submitReview(...a),
}));

function renderCard() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ReviewLearnedCard cycleId="c1" />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  submitReview.mockClear();
});

describe("ReviewLearnedCard", () => {
  it("groups what was learned with Olympus's suggestion preselected", async () => {
    renderCard();
    expect(await screen.findByText("Is this what your app does?")).toBeInTheDocument();
    expect(screen.getByText("Features")).toBeInTheDocument();
    expect(screen.getByText("No passing test proves this behavior yet.")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Yes, this is a feature" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("radio", { name: "Don't protect it" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("confirms the suggestions in one click", async () => {
    renderCard();
    fireEvent.click(await screen.findByRole("button", { name: "Looks right, confirm" }));
    await waitFor(() => expect(submitReview).toHaveBeenCalledTimes(1));
    expect(submitReview.mock.calls[0]).toEqual([
      "c1",
      [
        { subject_type: "FEATURE_SPEC", subject_id: "f1", choice: "keep" },
        { subject_type: "BASELINE", subject_id: "b1", choice: "drop" },
      ],
    ]);
  });

  it("sends the person's corrections", async () => {
    renderCard();
    fireEvent.click(await screen.findByRole("radio", { name: "No, not a real feature" }));
    const confirm = screen.getByRole("button", { name: "Confirm (1 changed)" });
    fireEvent.click(confirm);
    await waitFor(() => expect(submitReview).toHaveBeenCalledTimes(1));
    expect(submitReview.mock.calls[0][1][0]).toEqual({
      subject_type: "FEATURE_SPEC",
      subject_id: "f1",
      choice: "drop",
    });
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExpectedBehaviorDecisionPreview } from "@/components/studio/decision/ExpectedBehaviorDecisionPreview";
import type { ExpectedBehaviorReview } from "@/src/api/types/journey";

let review: { isLoading: boolean; isError: boolean; data: ExpectedBehaviorReview | null };

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useExpectedBehaviorReview: () => review,
}));

const payload: ExpectedBehaviorReview = {
  resolution_id: "res-1",
  classification: "UNDERSPECIFIED",
  statement: "Deleting a non-empty column must be refused with 409.",
  proposed_ac: {
    statement: "Deleting a column that still has cards is refused",
    given: "a column with two cards",
    when: "the user deletes the column",
    then: "the API responds 409 and no cards are deleted",
  },
  questions: ["Should archived cards count as cards?"],
  cited_acceptance_criteria: [],
  contradicted_baselines: [
    {
      id: "bl-1",
      lineage_key: "columns.delete.cascade",
      given: "a column with cards",
      when: "the column is deleted",
      then: "its cards are deleted too",
      status: "ACTIVE",
    },
  ],
  approval_id: "apr-1",
};

afterEach(() => {
  cleanup();
});

describe("ExpectedBehaviorDecisionPreview", () => {
  it("shows classification, statement, proposed AC, questions and contradicted baselines", () => {
    review = { isLoading: false, isError: false, data: payload };
    render(<ExpectedBehaviorDecisionPreview resolutionId="res-1" />);

    expect(screen.getByText("UNDERSPECIFIED")).toBeTruthy();
    expect(screen.getByText(payload.statement)).toBeTruthy();

    expect(screen.getByText("Proposed acceptance criterion")).toBeTruthy();
    expect(screen.getByText("Deleting a column that still has cards is refused")).toBeTruthy();
    expect(screen.getByText("a column with two cards")).toBeTruthy();
    expect(screen.getByText("the user deletes the column")).toBeTruthy();
    expect(screen.getByText("the API responds 409 and no cards are deleted")).toBeTruthy();

    expect(screen.getByText("Should archived cards count as cards?")).toBeTruthy();

    expect(screen.getByText("columns.delete.cascade · ACTIVE")).toBeTruthy();
    expect(screen.getByText("a column with cards")).toBeTruthy();
    expect(screen.getByText("the column is deleted")).toBeTruthy();
    expect(screen.getByText("its cards are deleted too")).toBeTruthy();
    expect(screen.queryByText("—")).toBeNull();
  });

  it("states when nothing is proposed, asked or contradicted", () => {
    review = {
      isLoading: false,
      isError: false,
      data: { ...payload, proposed_ac: null, questions: [], contradicted_baselines: [] },
    };
    render(<ExpectedBehaviorDecisionPreview resolutionId="res-1" />);
    expect(screen.getByText("No new acceptance criterion proposed.")).toBeTruthy();
    expect(screen.getByText("No open questions.")).toBeTruthy();
    expect(screen.getByText("No baselines contradicted.")).toBeTruthy();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProvisionalBaselinesPanel } from "@/components/studio/ProvisionalBaselinesPanel";
import type { BehavioralBaselineSummary } from "@/src/api/types/journey";

let baselines: BehavioralBaselineSummary[] = [];

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useProjectBaselines: () => ({ data: baselines, isLoading: false }),
}));

function baseline(overrides: Partial<BehavioralBaselineSummary>): BehavioralBaselineSummary {
  return {
    id: "bl-1",
    lineage_key: "columns.delete.cascade",
    version: 1,
    status: "ACTIVE",
    source: "CHARACTERIZATION",
    check_kind: "TEST",
    check_ref: "tests/test_columns.py::test_delete_cascades",
    established_sha: "abc123",
    feature_spec_id: null,
    provisional: false,
    provisional_known_gaps: [],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  baselines = [];
});

describe("ProvisionalBaselinesPanel", () => {
  it("shows the Provisional badge in words with the known gap it rests on", () => {
    baselines = [
      baseline({
        id: "bl-prov",
        lineage_key: "cards.move.order",
        provisional: true,
        provisional_known_gaps: ["Card ordering across columns is not specified"],
      }),
      baseline({ id: "bl-firm", lineage_key: "columns.create" }),
    ];
    render(<ProvisionalBaselinesPanel projectId="proj-1" />);
    expect(screen.getByText("Provisional")).toBeTruthy();
    expect(screen.getByText("cards.move.order")).toBeTruthy();
    expect(screen.getByText("Card ordering across columns is not specified")).toBeTruthy();
    expect(screen.queryByText("columns.create")).toBeNull();
  });

  it("renders nothing when no baseline is provisional", () => {
    baselines = [baseline({})];
    const { container } = render(<ProvisionalBaselinesPanel projectId="proj-1" />);
    expect(container.innerHTML).toBe("");
    expect(screen.queryByText("Provisional")).toBeNull();
  });
});

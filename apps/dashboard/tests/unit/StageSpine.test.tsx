import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StageSpine } from "@/components/studio/StageSpine";

describe("StageSpine", () => {
  it("renders greenfield stages and selects via callback only", () => {
    const onSelect = vi.fn();
    render(
      <StageSpine
        cycleType="GREENFIELD_BUILD"
        cycleState="DISCOVERY"
        selectedStage="DISCOVERY"
        inboxStages={new Set()}
        nextTransitions={[]}
        onSelectStage={onSelect}
      />,
    );
    expect(screen.getByRole("button", { name: /Product model/i })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Product model/i }));
    expect(onSelect).toHaveBeenCalledWith("PRODUCT_MODEL");
  });

  it("renders different spine length for brownfield", () => {
    const { rerender } = render(
      <StageSpine
        cycleType="GREENFIELD_BUILD"
        cycleState="DISCOVERY"
        selectedStage="DISCOVERY"
        inboxStages={new Set()}
        nextTransitions={[]}
        onSelectStage={() => {}}
      />,
    );
    const greenCount = screen.getAllByRole("button").length;
    rerender(
      <StageSpine
        cycleType="BROWNFIELD_ONBOARDING"
        cycleState="RECON"
        selectedStage="RECON"
        inboxStages={new Set()}
        nextTransitions={[]}
        onSelectStage={() => {}}
      />,
    );
    expect(screen.getAllByRole("button").length).not.toBe(greenCount);
  });
});

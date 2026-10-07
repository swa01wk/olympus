import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { NextStepBar } from "@/components/studio/NextStepBar";
import type { TransitionPreview } from "@/src/api/types/core";

const base: TransitionPreview = {
  command: "start_architecture",
  to_state: "ARCHITECTURE",
  target_state: "ARCHITECTURE",
  allowed: false,
  guard_preview: [],
  guard_results: [{ guard_id: "scope_approved", ok: false, reasons: ["SCOPE pending"] }],
  authorization_denied: false,
};

afterEach(() => cleanup());

describe("NextStepBar", () => {
  it("disables primary advance until allowed", () => {
    render(
      <NextStepBar
        cycleId="c1"
        cycleState="PRODUCT_MODEL"
        nextTransitions={[base]}
        onTransition={() => {}}
      />,
    );
    expect(screen.getByText(/scope_approved/i)).toBeTruthy();
    const primary = screen.getByRole("button", { name: /start_architecture/i });
    expect(primary).toHaveProperty("disabled", true);
  });

  it("enables primary when guard passes without reload", () => {
    render(
      <NextStepBar
        cycleId="c1"
        cycleState="PRODUCT_MODEL"
        nextTransitions={[{ ...base, allowed: true, guard_results: [{ guard_id: "scope_approved", ok: true, reasons: [] }] }]}
        onTransition={() => {}}
      />,
    );
    const primary = screen.getByRole("button", { name: /start_architecture/i });
    expect(primary).toHaveProperty("disabled", false);
  });

  it("shows guard failure reasons", () => {
    render(
      <NextStepBar
        cycleId="c1"
        cycleState="PRODUCT_MODEL"
        nextTransitions={[base]}
        onTransition={() => {}}
      />,
    );
    expect(screen.getByText(/SCOPE pending/i)).toBeTruthy();
  });
});

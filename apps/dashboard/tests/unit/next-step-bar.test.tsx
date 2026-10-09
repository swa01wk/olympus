import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

  it("keeps cancel and fail out of the primary slot", () => {
    const sideExit = (command: string, to_state: string): TransitionPreview => ({
      ...base,
      command,
      to_state,
      target_state: to_state,
      allowed: true,
      guard_results: [],
    });
    render(
      <NextStepBar
        cycleId="c1"
        cycleState="PRODUCT_MODEL"
        nextTransitions={[
          sideExit("cancel", "CANCELLED"),
          { ...sideExit("fail", "FAILED"), authorization_denied: true },
          { ...base, allowed: true, guard_results: [] },
        ]}
        onTransition={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /start_architecture/i })).toHaveProperty(
      "disabled",
      false,
    );
    expect(screen.queryByRole("button", { name: /fail → FAILED/i })).toBeNull();
  });

  it("prefers the allowed forward command and lists the other under More commands", () => {
    const remediation: TransitionPreview = {
      ...base,
      command: "start_remediation",
      to_state: "REMEDIATION",
      target_state: "REMEDIATION",
      allowed: false,
      guard_results: [{ guard_id: "readiness_failed_remediable", ok: false, reasons: ["READY"] }],
    };
    const declare: TransitionPreview = {
      ...base,
      command: "declare_ready",
      to_state: "READY",
      target_state: "READY",
      allowed: true,
      guard_results: [{ guard_id: "readiness_assessment_ready", ok: true, reasons: [] }],
    };
    render(
      <NextStepBar
        cycleId="c1"
        cycleState="READINESS"
        nextTransitions={[remediation, declare]}
        onTransition={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /declare_ready → READY/i })).toHaveProperty(
      "disabled",
      false,
    );
    fireEvent.click(screen.getByRole("button", { name: "More commands" }));
    expect(screen.getByRole("button", { name: /start_remediation/i })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("leads with a runnable same-state retry when the forward command is blocked", () => {
    const baseline: TransitionPreview = {
      ...base,
      command: "start_baseline",
      to_state: "BASELINE",
      target_state: "BASELINE",
      allowed: false,
      guard_results: [
        { guard_id: "recovery_proposal_persisted", ok: false, reasons: ["RECOVERY_PROPOSAL_MISSING"] },
      ],
    };
    const retry: TransitionPreview = {
      ...base,
      command: "retry_spec_recovery",
      to_state: "RECOVERED_SPEC",
      target_state: "RECOVERED_SPEC",
      allowed: true,
      guard_results: [{ guard_id: "recovery_proposal_rejected", ok: true, reasons: [] }],
    };
    render(
      <NextStepBar
        cycleId="c1"
        cycleState="RECOVERED_SPEC"
        nextTransitions={[baseline, retry]}
        onTransition={() => {}}
      />,
    );
    expect(
      screen.getByRole("button", { name: /retry_spec_recovery → RECOVERED SPEC/i }),
    ).toHaveProperty("disabled", false);
    fireEvent.click(screen.getByRole("button", { name: "More commands" }));
    expect(screen.getByRole("button", { name: /start_baseline/i })).toHaveProperty(
      "disabled",
      true,
    );
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

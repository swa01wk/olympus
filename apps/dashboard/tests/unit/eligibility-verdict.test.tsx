import { render } from "@testing-library/react";
import { screen } from "@testing-library/dom";
import { describe, expect, it } from "vitest";
import { EligibilityVerdict } from "@/components/release/EligibilityVerdict";

describe("EligibilityVerdict", () => {
  it("shows RELEASE BLOCKED from server eligible flag only", () => {
    render(
      <EligibilityVerdict
        evaluation={{
          delivery_cycle_id: "11111111-1111-4111-8111-111111111204",
          integration_candidate_id: "11111111-1111-4111-8111-111111111302",
          eligible: false,
          conditions: [{ name: "required_gates_pass", ok: false, reasons: ["Sentinel FAIL"] }],
        }}
      />,
    );
    expect(screen.getByText("RELEASE BLOCKED")).toBeInTheDocument();
  });
});

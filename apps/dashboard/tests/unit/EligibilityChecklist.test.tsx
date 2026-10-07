import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EligibilityChecklist } from "@/components/assurance/EligibilityChecklist";

describe("EligibilityChecklist", () => {
  it("shows blocked when not eligible", () => {
    render(
      <EligibilityChecklist
        eligible={false}
        conditions={[{ name: "proof.ready", ok: false, reasons: ["missing evidence"] }]}
      />,
    );
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("missing evidence")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceMatrix } from "@/components/assurance/EvidenceMatrix";

describe("EvidenceMatrix", () => {
  it("labels stale SHA rows", () => {
    render(
      <EvidenceMatrix
        obligations={[{ id: "o1", subject_key: "ac-1", status: "OPEN" }]}
        evidence={[{ id: "e1", key: "ev-1", commit_sha: "aaa111", result: "PASS" }]}
        coverage={[
          { obligation_id: "o1", evidence_id: "e1", satisfied: false },
        ]}
        targetSha="bbb222"
      />,
    );
    expect(screen.getByText("Not current target")).toBeInTheDocument();
  });
});

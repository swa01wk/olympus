import { describe, expect, it } from "vitest";
import { laneForRecordKind, LANES, laneIndex } from "@/src/control-plane/lanes";

describe("lanes config", () => {
  it("has six lanes in design order", () => {
    expect(LANES.map((l) => l.code)).toEqual(["IN", "WK", "EX", "CD", "EV", "OU"]);
  });

  it("maps IntegrationCandidate to code lane", () => {
    expect(laneForRecordKind("IntegrationCandidate")).toBe("code");
  });

  it("laneIndex is stable", () => {
    expect(laneIndex("evidence")).toBe(4);
  });
});

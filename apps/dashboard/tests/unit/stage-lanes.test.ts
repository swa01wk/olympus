import { describe, expect, it } from "vitest";
import {
  laneForCycleState,
  ribbonStages,
  stageIndex,
  stagesForCycleType,
} from "@/src/control-plane/stage-lanes";

describe("stage-lanes", () => {
  it("maps greenfield DEVELOPMENT to EX lane", () => {
    const row = laneForCycleState("GREENFIELD_BUILD", "DEVELOPMENT");
    expect(row?.laneCode).toBe("EX");
  });

  it("orders bug fix reproduction in EV lane", () => {
    const stages = stagesForCycleType("BUG_FIX");
    expect(stages.find((s) => s.state === "REPRODUCTION")?.laneCode).toBe("EV");
  });

  it("ribbon never includes future stages beyond current", () => {
    const ribbon = ribbonStages("FEATURE_CHANGE", "PLANNING");
    expect(ribbon.at(-1)?.state).toBe("PLANNING");
    expect(ribbon.some((s) => s.state === "RELEASE")).toBe(false);
  });

  it("stageIndex finds architecture on greenfield", () => {
    expect(stageIndex("GREENFIELD_BUILD", "ARCHITECTURE")).toBe(2);
  });
});

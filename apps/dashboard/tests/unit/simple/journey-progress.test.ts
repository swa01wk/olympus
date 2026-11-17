import { describe, expect, it } from "vitest";
import { journeyName, journeyStages } from "@/lib/journey-progress";

describe("journeyStages", () => {
  it("marks earlier stages done and the current one active", () => {
    const stages = journeyStages("GREENFIELD_BUILD", "PLANNING");
    expect(stages.map((s) => [s.id, s.status])).toEqual([
      ["features", "done"],
      ["design", "done"],
      ["plan", "current"],
      ["build", "upcoming"],
      ["check", "upcoming"],
      ["release", "upcoming"],
    ]);
  });

  it("groups several backend states into one plain stage", () => {
    expect(journeyStages("GREENFIELD_BUILD", "DISCOVERY")[0].status).toBe("current");
    expect(journeyStages("GREENFIELD_BUILD", "INTEGRATION")[4].status).toBe("current");
    expect(journeyStages("GREENFIELD_BUILD", "ASSURANCE")[4].status).toBe("current");
  });

  it("shows everything done once the app is released", () => {
    expect(journeyStages("GREENFIELD_BUILD", "COMPLETE").every((s) => s.status === "done")).toBe(
      true,
    );
  });

  it("maps onboarding states to plain stages", () => {
    const stages = journeyStages("BROWNFIELD_ONBOARDING", "BASELINE");
    expect(stages.map((s) => s.status)).toEqual(["done", "done", "done", "current", "upcoming"]);
    expect(journeyStages("BROWNFIELD_ONBOARDING", "READY").every((s) => s.status === "done")).toBe(
      true,
    );
    expect(journeyName("BROWNFIELD_ONBOARDING")).toBe("Existing repo");
  });

  it("has no stages for journeys Autopilot does not cover yet", () => {
    expect(journeyStages("BUG_FIX", "TRIAGE")).toEqual([]);
    expect(journeyName("BUG_FIX")).toBe("Bug fix");
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseFxParam, formatFxParam } from "@/lib/api/fx-param";
import { getScenarioControllerImpl } from "@/lib/fixtures/controller";
import { clearWorldCache } from "@/lib/fixtures/engine/build-world";
import { resetFixtureStore } from "@/lib/fixtures/store";

describe("parseFxParam", () => {
  it("parses scenario:checkpoint", () => {
    expect(parseFxParam("feature-change:05-development-running")).toEqual({
      scenarioId: "feature-change",
      checkpointId: "05-development-running",
    });
  });
  it("round-trips format", () => {
    const fx = formatFxParam("greenfield", "00-intake");
    expect(parseFxParam(fx)?.checkpointId).toBe("00-intake");
  });
});

describe("ScenarioController", () => {
  beforeEach(() => {
    clearWorldCache();
    resetFixtureStore();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    getScenarioControllerImpl().setPlaying(false);
  });

  it("next and previous move checkpoints", () => {
    const c = getScenarioControllerImpl();
    c.setPosition("feature-change", "00-intake");
    const n = c.next();
    expect(n.checkpointIndex).toBe(1);
    const p = c.previous();
    expect(p.checkpointId).toBe("00-intake");
  });

  it("reset returns to first checkpoint of current scenario", () => {
    const c = getScenarioControllerImpl();
    c.setPosition("bug-fix", "11-released");
    const r = c.reset();
    expect(r.scenarioId).toBe("bug-fix");
    expect(r.checkpointIndex).toBe(0);
  });
});

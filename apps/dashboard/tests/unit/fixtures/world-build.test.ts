import { describe, expect, it } from "vitest";
import { buildWorld, clearWorldCache } from "@/lib/fixtures/engine/build-world";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";
import { DeliveryCycle } from "@/lib/contracts/entities";

describe("buildWorld", () => {
  it("builds every scenario checkpoint deterministically", () => {
    for (const [scenarioId, checkpoints] of Object.entries(SCENARIO_CHECKPOINTS)) {
      for (const cp of checkpoints) {
        clearWorldCache();
        const a = buildWorld(scenarioId as keyof typeof SCENARIO_CHECKPOINTS, cp.index);
        clearWorldCache();
        const b = buildWorld(scenarioId as keyof typeof SCENARIO_CHECKPOINTS, cp.index);
        expect(a).toEqual(b);
        expect(() => a.cycles.forEach((c) => DeliveryCycle.parse(c))).not.toThrow();
        expect(a.project.id).toBeTruthy();
      }
    }
  });
});

import { describe, expect, it } from "vitest";
import { buildWorld } from "@/lib/fixtures/engine/build-world";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";

describe("secrets and host paths", () => {
  it("world JSON has no /var/olympus host paths", () => {
    for (const [scenarioId, checkpoints] of Object.entries(SCENARIO_CHECKPOINTS)) {
      for (const cp of checkpoints) {
        const world = buildWorld(scenarioId as keyof typeof SCENARIO_CHECKPOINTS, cp.index);
        const blob = JSON.stringify(world);
        expect(blob).not.toMatch(/\/var\/olympus/);
        expect(blob).not.toMatch(/BEGIN (RSA|OPENSSH) PRIVATE KEY/);
      }
    }
  });
});

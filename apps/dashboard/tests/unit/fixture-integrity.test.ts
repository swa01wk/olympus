import { describe, expect, it } from "vitest";
import { buildSupportDeskChained } from "@/lib/fixtures/scenarios/supportdesk";
import { DeliveryCycle, Release, Task } from "@/lib/contracts/entities";

describe("SupportDesk fixture integrity", () => {
  it("has coherent release vs cycle states", () => {
    const seed = buildSupportDeskChained();
    const cycleById = new Map(seed.cycles.map((c) => [c.id, c]));
    for (const r of seed.releases) {
      const cycle = cycleById.get(r.delivery_cycle_id);
      expect(cycle).toBeTruthy();
      if (r.status === "RELEASED") {
        expect(["COMPLETE", "READY"].includes(cycle!.state)).toBe(true);
      }
      if (cycle!.state === "DEVELOPMENT" && r.key === "R2") {
        expect(r.status).not.toBe("RELEASED");
      }
    }
  });

  it("every task references an existing cycle", () => {
    const seed = buildSupportDeskChained();
    const cycleIds = new Set(seed.cycles.map((c) => c.id));
    for (const t of seed.tasks) {
      expect(cycleIds.has(t.delivery_cycle_id)).toBe(true);
    }
  });

  it("parses core entities with zod", () => {
    const seed = buildSupportDeskChained();
    expect(() => seed.cycles.forEach((c) => DeliveryCycle.parse(c))).not.toThrow();
    expect(() => seed.tasks.forEach((t) => Task.parse(t))).not.toThrow();
    expect(() => seed.releases.forEach((r) => Release.parse(r))).not.toThrow();
  });
});

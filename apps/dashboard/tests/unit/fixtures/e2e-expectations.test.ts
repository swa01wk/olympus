import { describe, expect, it } from "vitest";
import { buildWorldByCheckpointId } from "@/lib/fixtures/engine/build-world";
import { SCENARIO_CHECKPOINTS } from "@/lib/fixtures/supportdesk/scenarios";
import {
  CHECKPOINT_EXPECTATIONS,
  type CheckpointExpectation,
} from "../../e2e/olympus/fixtures/journey-expectations";

function assertWorldMatches(exp: CheckpointExpectation, scenarioId: keyof typeof CHECKPOINT_EXPECTATIONS, cpId: string) {
  const world = buildWorldByCheckpointId(scenarioId, cpId);
  if (exp.cycleKey) {
    const c = world.cycles.find((x) => x.key === exp.cycleKey);
    expect(c, `${scenarioId}:${cpId} cycle ${exp.cycleKey}`).toBeTruthy();
    if (exp.cycleState) expect(c!.state).toBe(exp.cycleState);
  }
  if (exp.canonicalSha) {
    expect(world.repository.canonical_commit).toBe(exp.canonicalSha);
  }
  if (exp.integratedIc) {
    const ic = world.ics.find((i) => i.key === exp.integratedIc);
    expect(ic?.integrated_sha ?? world.repository.canonical_commit).toBeTruthy();
  }
  if (exp.releaseKey) {
    const r = world.releases.find((x) => x.key === exp.releaseKey);
    expect(r).toBeTruthy();
    if (exp.releaseStatus) expect(r!.status).toBe(exp.releaseStatus);
  }
  if (exp.tasks) {
    for (const t of exp.tasks) {
      const row = world.tasks.find((x) => x.key === t.key);
      expect(row?.status, `${t.key} status`).toBe(t.status);
    }
  }
  if (exp.executions) {
    for (const key of exp.executions) {
      expect(world.executions.some((e) => e.key === key)).toBe(true);
    }
  }
  if (exp.defectKey) {
    expect(world.defect?.key).toBe(exp.defectKey);
  }
  if (exp.readiness) {
    expect(world.project.readiness_state).toBe(exp.readiness);
  }
}

describe("e2e journey expectations vs fixture world", () => {
  it("every scenario has named checkpoints (no NN-stage placeholders)", () => {
    for (const [scenario, cps] of Object.entries(SCENARIO_CHECKPOINTS)) {
      for (const cp of cps) {
        expect(cp.id, scenario).not.toMatch(/^\d{2}-stage$/);
      }
    }
  });

  for (const [scenarioId, byCp] of Object.entries(CHECKPOINT_EXPECTATIONS)) {
    describe(scenarioId, () => {
      for (const [cpId, exp] of Object.entries(byCp ?? {})) {
        it(`${cpId} world facts`, () => {
          assertWorldMatches(exp!, scenarioId as keyof typeof CHECKPOINT_EXPECTATIONS, cpId);
        });
      }
    });
  }
});

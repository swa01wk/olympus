import { describe, expect, it } from "vitest";
import { buildWorld } from "@/lib/fixtures/engine/build-world";
import { SHAS } from "@/lib/fixtures/supportdesk/shas";
import { IDS } from "@/lib/fixtures/ids";

describe("consistency rules (feature-change @ development)", () => {
  const world = buildWorld("feature-change", 5);

  it("TASK-221 execution EX-551 aligns with base 73fb91d", () => {
    const task = world.tasks.find((t) => t.key === "TASK-221");
    const ex = world.executions.find((e) => e.key === "EX-551");
    expect(task).toBeTruthy();
    expect(ex?.task_id).toBe(task!.id);
    const ws = world.executionWorkspaces.find((w) => w.execution_id === ex!.id);
    expect(ws?.base_commit).toBe(SHAS.r1Integrated);
    const dc = world.cycles.find((c) => c.key === "DC-003");
    expect(dc?.base_sha).toBe(SHAS.r1Integrated);
  });
});

describe("consistency rules (feature-change released)", () => {
  const world = buildWorld("feature-change", 11);

  it("IC-003 READY sets canonical r2-def456", () => {
    const ic3 = world.ics.find((i) => i.key === "IC-003");
    expect(ic3?.integrated_sha).toBe(SHAS.r2Integrated);
    expect(world.repository.canonical_commit).toBe(SHAS.r2Integrated);
    const r2 = world.releases.find((r) => r.key === "R2");
    expect(r2?.integrated_sha).toBe(SHAS.r2Integrated);
    expect(r2?.integration_candidate_id).toBe(IDS.ic003);
  });
});

describe("consistency rules (bug-fix released)", () => {
  const world = buildWorld("bug-fix", 11);

  it("IC-005 supersedes IC-004 for R3", () => {
    const ic5 = world.ics.find((i) => i.key === "IC-005");
    expect(ic5?.integrated_sha).toBe(SHAS.r3Integrated);
    expect(world.repository.released_commit).toBe(SHAS.r3Integrated);
    const ic4 = world.ics.find((i) => i.key === "IC-004");
    expect(ic4?.status).toBe("SUPERSEDED");
  });
});

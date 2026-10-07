import { describe, expect, it } from "vitest";
import {
  findPendingApprovalForStage,
  inboxStagesForCycle,
  isCycleStageBlocked,
  spineStatusForStage,
} from "@/lib/studio-spine";
import type { InboxItem } from "@/src/api/types/core";
import { STAGES_BY_CYCLE_TYPE } from "@/src/control-plane/stage-lanes";

describe("STAGES_BY_CYCLE_TYPE", () => {
  it("differs between greenfield and bug fix", () => {
    expect(STAGES_BY_CYCLE_TYPE.GREENFIELD_BUILD[0]).toBe("DISCOVERY");
    expect(STAGES_BY_CYCLE_TYPE.BUG_FIX[0]).toBe("TRIAGE");
    expect(STAGES_BY_CYCLE_TYPE.GREENFIELD_BUILD).not.toEqual(STAGES_BY_CYCLE_TYPE.BUG_FIX);
  });
});

describe("spineStatusForStage", () => {
  const greenfield = STAGES_BY_CYCLE_TYPE.GREENFIELD_BUILD;

  it("marks earlier stages done", () => {
    expect(
      spineStatusForStage("DISCOVERY", "PLANNING", greenfield, {
        inboxStages: new Set(),
        nextTransitions: [],
      }),
    ).toBe("done");
  });

  it("marks later stages future", () => {
    expect(
      spineStatusForStage("RELEASE", "PLANNING", greenfield, {
        inboxStages: new Set(),
        nextTransitions: [],
      }),
    ).toBe("future");
  });

  it("marks current stage when transitions allow", () => {
    expect(
      spineStatusForStage("PLANNING", "PLANNING", greenfield, {
        inboxStages: new Set(),
        nextTransitions: [{ command: "start_development", to_state: "DEVELOPMENT", allowed: true } as never],
      }),
    ).toBe("current");
  });

  it("marks waiting when inbox maps to stage", () => {
    expect(
      spineStatusForStage("PRODUCT_MODEL", "PRODUCT_MODEL", greenfield, {
        inboxStages: new Set(["PRODUCT_MODEL"]),
        nextTransitions: [],
      }),
    ).toBe("waiting");
  });

  it("marks blocked when current and all forward transitions disallowed", () => {
    expect(
      isCycleStageBlocked("PLANNING", "PLANNING", [
        { command: "start_development", to_state: "DEVELOPMENT", allowed: false } as never,
      ]),
    ).toBe(true);
    expect(
      spineStatusForStage("PLANNING", "PLANNING", greenfield, {
        inboxStages: new Set(),
        nextTransitions: [
          { command: "start_development", to_state: "DEVELOPMENT", allowed: false } as never,
        ],
      }),
    ).toBe("blocked");
  });
});

describe("inboxStagesForCycle", () => {
  it("maps SCOPE approval to PRODUCT_MODEL", () => {
    const stages = inboxStagesForCycle([
      {
        kind: "APPROVAL",
        id: "a1",
        title: "Scope",
        approval: {
          id: "a1",
          key: "APR-1",
          approval_type: "SCOPE",
          subject_type: "scope",
          subject_id: "s1",
          subject_hash: "h",
          status: "PENDING",
        },
      },
    ]);
    expect(stages.has("PRODUCT_MODEL")).toBe(true);
  });
});

describe("findPendingApprovalForStage", () => {
  const inbox: InboxItem[] = [
    {
      kind: "APPROVAL",
      id: "i1",
      title: "Scope",
      approval: {
        id: "a1",
        key: "APR-1",
        approval_type: "SCOPE",
        subject_type: "ScopeBundle",
        subject_id: "s1",
        subject_hash: "hash",
        status: "PENDING",
      },
    },
  ];

  it("returns approval when stage matches type map", () => {
    expect(findPendingApprovalForStage(inbox, "PRODUCT_MODEL")?.key).toBe("APR-1");
  });

  it("returns null for unrelated stage", () => {
    expect(findPendingApprovalForStage(inbox, "DISCOVERY")).toBeNull();
  });
});

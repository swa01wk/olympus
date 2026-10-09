import { describe, expect, it } from "vitest";
import {
  approvalStage,
  findChangesRequestedApprovalForStage,
  findPendingApprovalForStage,
  inboxStagesForCycle,
  isCycleStageBlocked,
  spineStatusForStage,
} from "@/lib/studio-spine";
import type { InboxItem } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { STAGES_BY_CYCLE_TYPE } from "@/src/control-plane/stage-lanes";

const CYCLE_TYPES: DeliveryCycleType[] = [
  "GREENFIELD_BUILD",
  "BROWNFIELD_ONBOARDING",
  "FEATURE_CHANGE",
  "BUG_FIX",
  "REMEDIATION",
];

describe("STAGES_BY_CYCLE_TYPE", () => {
  it("differs between greenfield and bug fix", () => {
    expect(STAGES_BY_CYCLE_TYPE.GREENFIELD_BUILD[0]).toBe("DISCOVERY");
    expect(STAGES_BY_CYCLE_TYPE.BUG_FIX[0]).toBe("TRIAGE");
    expect(STAGES_BY_CYCLE_TYPE.GREENFIELD_BUILD).not.toEqual(STAGES_BY_CYCLE_TYPE.BUG_FIX);
  });
});

describe("approvalStage", () => {
  const cases: [string, DeliveryCycleType, string | null][] = [
    ["IMPLEMENTATION_SPEC", "GREENFIELD_BUILD", "PLANNING"],
    ["IMPLEMENTATION_SPEC", "FEATURE_CHANGE", "PLANNING"],
    ["IMPLEMENTATION_SPEC", "REMEDIATION", "PLANNING"],
    ["IMPLEMENTATION_SPEC", "BUG_FIX", "ROOT_CAUSE"],
    ["IMPLEMENTATION_SPEC", "BROWNFIELD_ONBOARDING", "REMEDIATION"],
    ["ARCHITECTURE_DELTA", "FEATURE_CHANGE", "IMPACT_ANALYSIS"],
    ["ARCHITECTURE", "GREENFIELD_BUILD", "ARCHITECTURE"],
    ["ARCHITECTURE", "BROWNFIELD_ONBOARDING", "BASELINE"],
    ["PROMOTION", "BROWNFIELD_ONBOARDING", "BASELINE"],
    ["SPEC_DELTA", "FEATURE_CHANGE", "SPEC_DELTA"],
    ["UNREPRODUCED_REPAIR", "BUG_FIX", "REPRODUCTION"],
    ["FINDING_WAIVER", "GREENFIELD_BUILD", "ASSURANCE"],
    ["ACTION", "GREENFIELD_BUILD", "DEVELOPMENT"],
    ["RELEASE", "GREENFIELD_BUILD", "RELEASE"],
    ["SCOPE", "GREENFIELD_BUILD", "PRODUCT_MODEL"],
    ["EXPECTED_BEHAVIOR", "BUG_FIX", "EXPECTED_BEHAVIOR"],
  ];

  it.each(cases)("maps %s on %s → %s", (approvalType, cycleType, stage) => {
    expect(approvalStage(approvalType, cycleType)).toBe(stage);
  });

  it("returns null for ARCHITECTURE_DELTA outside feature change", () => {
    for (const cycleType of CYCLE_TYPES) {
      if (cycleType === "FEATURE_CHANGE") continue;
      expect(approvalStage("ARCHITECTURE_DELTA", cycleType)).toBeNull();
    }
  });

  it("returns null for removed approval types", () => {
    for (const t of ["REPAIR_SPEC", "READINESS", "SPEC_DECISION", "DEPLOYMENT"] as const) {
      for (const cycleType of CYCLE_TYPES) {
        expect(approvalStage(t, cycleType)).toBeNull();
      }
    }
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
    const stages = inboxStagesForCycle(
      [
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
      ],
      "GREENFIELD_BUILD",
    );
    expect(stages.has("PRODUCT_MODEL")).toBe(true);
  });

  it("maps bug-fix repair spec to ROOT_CAUSE", () => {
    const stages = inboxStagesForCycle(
      [
        {
          kind: "APPROVAL",
          id: "a1",
          title: "Repair spec",
          approval: {
            id: "a1",
            key: "APR-2",
            approval_type: "IMPLEMENTATION_SPEC",
            subject_type: "ImplementationSpec",
            subject_id: "s1",
            subject_hash: "h",
            status: "PENDING",
          },
        },
      ],
      "BUG_FIX",
    );
    expect(stages.has("ROOT_CAUSE")).toBe(true);
    expect(stages.has("PLANNING")).toBe(false);
  });
});

describe("findChangesRequestedApprovalForStage", () => {
  const cr = {
    id: "apr-cr",
    approval_type: "SCOPE",
    status: "CHANGES_REQUESTED",
    delivery_cycle_id: "cyc-1",
    created_at: "2026-10-08T10:00:00Z",
  };

  it("matches CHANGES_REQUESTED approval on stage", () => {
    const hit = findChangesRequestedApprovalForStage([cr], "PRODUCT_MODEL", "GREENFIELD_BUILD", "cyc-1");
    expect(hit?.id).toBe("apr-cr");
  });

  it("returns null once a newer approval for the stage is PENDING or APPROVED", () => {
    for (const status of ["PENDING", "APPROVED"]) {
      const newer = { ...cr, id: "apr-new", status, created_at: "2026-10-08T11:00:00Z" };
      expect(
        findChangesRequestedApprovalForStage([newer, cr], "PRODUCT_MODEL", "GREENFIELD_BUILD", "cyc-1"),
      ).toBeNull();
    }
  });

  it("picks the newest CHANGES_REQUESTED regardless of list order", () => {
    const older = { ...cr, id: "apr-old", status: "APPROVED", created_at: "2026-10-08T09:00:00Z" };
    const newest = { ...cr, id: "apr-newest", created_at: "2026-10-08T12:00:00Z" };
    expect(
      findChangesRequestedApprovalForStage(
        [cr, newest, older],
        "PRODUCT_MODEL",
        "GREENFIELD_BUILD",
        "cyc-1",
      )?.id,
    ).toBe("apr-newest");
  });

  it("ignores newer approvals for other cycles or stages", () => {
    const otherCycle = { ...cr, id: "x1", status: "PENDING", delivery_cycle_id: "cyc-2", created_at: "2026-10-08T11:00:00Z" };
    const otherStage = { ...cr, id: "x2", approval_type: "ARCHITECTURE", status: "PENDING", created_at: "2026-10-08T11:00:00Z" };
    expect(
      findChangesRequestedApprovalForStage(
        [otherCycle, otherStage, cr],
        "PRODUCT_MODEL",
        "GREENFIELD_BUILD",
        "cyc-1",
      )?.id,
    ).toBe("apr-cr");
  });
});

describe("findPendingApprovalForStage", () => {
  const scopeInbox: InboxItem[] = [
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
    expect(
      findPendingApprovalForStage(scopeInbox, "PRODUCT_MODEL", "GREENFIELD_BUILD")?.key,
    ).toBe("APR-1");
  });

  it("returns null for unrelated stage", () => {
    expect(findPendingApprovalForStage(scopeInbox, "DISCOVERY", "GREENFIELD_BUILD")).toBeNull();
  });

  it("finds IMPLEMENTATION_SPEC at ROOT_CAUSE for bug fix", () => {
    const inbox: InboxItem[] = [
      {
        kind: "APPROVAL",
        id: "i1",
        title: "Repair",
        approval: {
          id: "a2",
          key: "APR-RC",
          approval_type: "IMPLEMENTATION_SPEC",
          subject_type: "ImplementationSpec",
          subject_id: "s1",
          subject_hash: "hash",
          status: "PENDING",
        },
      },
    ];
    expect(findPendingApprovalForStage(inbox, "ROOT_CAUSE", "BUG_FIX")?.key).toBe("APR-RC");
    expect(findPendingApprovalForStage(inbox, "PLANNING", "BUG_FIX")).toBeNull();
  });

  it("finds ARCHITECTURE_DELTA at IMPACT_ANALYSIS for feature change", () => {
    const inbox: InboxItem[] = [
      {
        kind: "APPROVAL",
        id: "i1",
        title: "Delta",
        approval: {
          id: "a3",
          key: "APR-AD",
          approval_type: "ARCHITECTURE_DELTA",
          subject_type: "Architecture",
          subject_id: "s1",
          subject_hash: "hash",
          status: "PENDING",
        },
      },
    ];
    expect(findPendingApprovalForStage(inbox, "IMPACT_ANALYSIS", "FEATURE_CHANGE")?.key).toBe(
      "APR-AD",
    );
    expect(findPendingApprovalForStage(inbox, "ARCHITECTURE", "FEATURE_CHANGE")).toBeNull();
  });
});

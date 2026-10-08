import { describe, expect, it } from "vitest";
import { parseChangesRequestedAudit } from "@/lib/changes-requested-audit";

describe("parseChangesRequestedAudit", () => {
  it("extracts note, actor and time from audit rows", () => {
    const view = parseChangesRequestedAudit([
      {
        id: "a1",
        action: "transition.accepted",
        actor_id: "actor-9",
        before: { status: "PENDING" },
        after: { status: "CHANGES_REQUESTED", note: "Clarify acceptance criteria" },
        occurred_at: "2026-10-08T12:00:00Z",
      },
    ]);
    expect(view?.note).toBe("Clarify acceptance criteria");
    expect(view?.actorId).toBe("actor-9");
    expect(view?.occurredAt).toBe("2026-10-08T12:00:00Z");
  });
});

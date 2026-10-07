import { describe, expect, it } from "vitest";
import type { OrchestratorSession, OrchestratorTurn } from "@/src/api/types/orchestrator";

describe("orchestrator types", () => {
  it("accepts assistant turn shape from backend session JSON", () => {
    const turn: OrchestratorTurn = {
      role: "assistant",
      text: "Proposed next step",
      execution_id: "ex-1",
      intent: "PROPOSE_COMMAND",
      proposal: {
        command: "decompose_source",
        target_ref: "src-1",
        args: { source_id: "src-1" },
        rationale: "Run decomposition",
      },
      clarification_answer_draft: null,
    };
    const session: OrchestratorSession = {
      id: "sess-1",
      project_id: "p1",
      delivery_cycle_id: "c1",
      expires_at: "2026-10-07T12:00:00Z",
      turns: [turn],
    };
    expect(session.turns[0].proposal?.command).toBe("decompose_source");
    expect(session.turns[0].clarification_answer_draft).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import {
  ATTENTION_ORDER,
  attentionPriority,
  mapBackendStatus,
  presentationForUiKey,
} from "@/src/adapters/status";

describe("status adapter", () => {
  it("maps TaskStatus BLOCKED to blocked UI key", () => {
    expect(mapBackendStatus("BLOCKED").uiKey).toBe("blocked");
    expect(mapBackendStatus("BLOCKED").glyph).toBe("⊘");
  });

  it("maps ExecutionStatus CHECKPOINTED", () => {
    expect(mapBackendStatus("CHECKPOINTED").uiKey).toBe("checkpointed");
  });

  it("orders checkpointed before blocked in attention", () => {
    expect(attentionPriority("checkpointed")).toBeLessThan(attentionPriority("blocked"));
    expect(ATTENTION_ORDER[0]).toBe("checkpointed");
  });

  it("falls back for unknown backend values", () => {
    const p = presentationForUiKey("custom-unknown");
    expect(p.label).toBeTruthy();
    expect(p.tone).toBe("neutral");
  });
});

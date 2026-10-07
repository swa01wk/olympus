import { describe, expect, it } from "vitest";
import { previewCycleCommand } from "@/lib/command-preview";

describe("command preview", () => {
  it("includes expected_state and idempotency key", () => {
    const s = previewCycleCommand("c1", "advance", "PLANNING", "idem-key-12345");
    expect(s).toContain("expected_state=PLANNING");
    expect(s).toContain("commands/advance");
    expect(s).toContain("idem-key-123");
  });
});

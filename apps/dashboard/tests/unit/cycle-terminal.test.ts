import { describe, expect, it } from "vitest";
import { isTerminalCycleState, terminalConsequence } from "@/lib/cycle-terminal";

describe("cycle-terminal", () => {
  it("recognizes terminal states", () => {
    expect(isTerminalCycleState("COMPLETE")).toBe(true);
    expect(isTerminalCycleState("PLANNING")).toBe(false);
  });

  it("returns consequence copy for FAILED", () => {
    expect(terminalConsequence("FAILED")).toMatch(/failed/i);
  });
});

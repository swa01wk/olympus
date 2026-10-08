import { describe, expect, it } from "vitest";
import { diffJsonBodies, diffLines, stableJsonLines } from "@/lib/json-line-diff";

describe("json-line-diff", () => {
  it("stableJsonLines sorts object keys", () => {
    const lines = stableJsonLines({ b: 1, a: 2 });
    expect(lines.some((l) => l.includes('"a"'))).toBe(true);
    expect(lines.join("\n")).toMatch(/"a": 2[\s\S]*"b": 1/);
  });

  it("diffLines marks add and remove", () => {
    const d = diffLines(["a", "b"], ["a", "c"]);
    expect(d.filter((x) => x.kind === "remove").map((x) => x.text)).toEqual(["b"]);
    expect(d.filter((x) => x.kind === "add").map((x) => x.text)).toEqual(["c"]);
  });

  it("diffJsonBodies compares pretty JSON bodies", () => {
    const d = diffJsonBodies({ x: 1 }, { x: 2 });
    expect(d.some((l) => l.kind === "remove" || l.kind === "add")).toBe(true);
  });
});

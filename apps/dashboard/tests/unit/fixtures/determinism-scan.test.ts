import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const FIXTURE_ROOT = path.join(process.cwd(), "lib/fixtures");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) return walk(p);
    return p.endsWith(".ts") ? [p] : [];
  });
}

describe("fixture determinism scan", () => {
  it("forbids non-deterministic APIs under lib/fixtures", () => {
    const forbidden = [
      /Date\.now\s*\(/,
      /Math\.random\s*\(/,
      /crypto\.randomUUID\s*\(/,
      /new Date\s*\(\s*\)/,
    ];
    const hits: string[] = [];
    for (const file of walk(FIXTURE_ROOT)) {
      const src = readFileSync(file, "utf8");
      for (const re of forbidden) {
        if (re.test(src)) hits.push(`${file}: ${re}`);
      }
    }
    expect(hits).toEqual([]);
  });
});

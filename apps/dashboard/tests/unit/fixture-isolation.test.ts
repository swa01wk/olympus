import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.join(process.cwd());
const SCAN_DIRS = ["app", "components"];

const FORBIDDEN = [
  /@\/lib\/fixtures\//,
  /from\s+["']@\/lib\/fixtures["']/,
  /from\s+["']@\/lib\/fixtures\/ids["']/,
];

function walk(dir: string, acc: string[] = []): string[] {
  if (!fs.existsSync(dir)) return acc;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full, acc);
    else if (/\.(tsx?|jsx?)$/.test(ent.name)) acc.push(full);
  }
  return acc;
}

describe("fixture isolation scan", () => {
  it("app/ and components/ do not import @/lib/fixtures", () => {
    const violations: string[] = [];
    for (const sub of SCAN_DIRS) {
      for (const file of walk(path.join(ROOT, sub))) {
        const text = fs.readFileSync(file, "utf8");
        for (const re of FORBIDDEN) {
          if (re.test(text)) {
            violations.push(`${path.relative(ROOT, file)}: ${re}`);
          }
        }
      }
    }
    expect(violations).toEqual([]);
  });
});

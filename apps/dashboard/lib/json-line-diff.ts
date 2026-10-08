/** Line-level diff for stable pretty-printed JSON (no external deps). */

export type DiffLineKind = "same" | "add" | "remove";

export type DiffLine = {
  kind: DiffLineKind;
  text: string;
};

export function stableJsonLines(value: unknown): string[] {
  return JSON.stringify(value, replacer, 2).split("\n");
}

function replacer(_key: string, val: unknown): unknown {
  if (val && typeof val === "object" && !Array.isArray(val)) {
    const obj = val as Record<string, unknown>;
    const sorted: Record<string, unknown> = {};
    for (const k of Object.keys(obj).sort()) {
      sorted[k] = obj[k];
    }
    return sorted;
  }
  return val;
}

/** Myers-style LCS backtracking on line arrays. */
export function diffLines(before: string[], after: string[]): DiffLine[] {
  const n = before.length;
  const m = after.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0) as number[]);
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      if (before[i] === after[j]) dp[i]![j] = dp[i + 1]![j + 1]! + 1;
      else dp[i]![j] = Math.max(dp[i + 1]![j]!, dp[i]![j + 1]!);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (before[i] === after[j]) {
      out.push({ kind: "same", text: before[i]! });
      i += 1;
      j += 1;
    } else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) {
      out.push({ kind: "remove", text: before[i]! });
      i += 1;
    } else {
      out.push({ kind: "add", text: after[j]! });
      j += 1;
    }
  }
  while (i < n) {
    out.push({ kind: "remove", text: before[i]! });
    i += 1;
  }
  while (j < m) {
    out.push({ kind: "add", text: after[j]! });
    j += 1;
  }
  return out;
}

export function diffJsonBodies(beforeBody: unknown, afterBody: unknown): DiffLine[] {
  return diffLines(stableJsonLines(beforeBody), stableJsonLines(afterBody));
}

/** Deterministic UUID-shaped ids and SHAs for fixture worlds (no randomness). */

function fnv1a(str: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function fid(namespace: string, key: string): string {
  const a = fnv1a(`${namespace}:${key}:a`).toString(16).padStart(8, "0");
  const b = fnv1a(`${namespace}:${key}:b`).toString(16).padStart(4, "0");
  const c = fnv1a(`${namespace}:${key}:c`).toString(16).padStart(4, "0");
  const d = ((fnv1a(`${namespace}:${key}:d`) & 0x0fff) | 0x4000).toString(16).padStart(4, "0");
  const e = fnv1a(`${namespace}:${key}:e`).toString(16).padStart(12, "0");
  return `${a}-${b}-${c}-${d}-${e}`;
}

const SHA_PAD = "0000000000000000000000000000000000000000";

const KNOWN_SHA_LABELS: Record<string, string> = {
  "gf-init-001": "0000000000000000000000000000000000000001",
  "73fb91d": "73fb91d00000000000000000000000000000001",
  "r2-def456": "r2def456000000000000000000000000000001",
  "982af11": "982af11000000000000000000000000000001",
  "r3-a41c9e0": "r3a41c9e000000000000000000000000000001",
  aaa5511: "aaa551100000000000000000000000000000001",
  bbb5522: "bbb552200000000000000000000000000000002",
  ccc5533: "ccc553300000000000000000000000000000003",
  ddd5544: "ddd554400000000000000000000000000000004",
  "5e1f0aa": "5e1f0aa00000000000000000000000000000001",
  "6c2d0b7": "6c2d0b70000000000000000000000000000001",
};

export function shaFor(label: string): string {
  if (KNOWN_SHA_LABELS[label]) return KNOWN_SHA_LABELS[label];
  if (label.length <= 12 && /^[a-f0-9-]+$/i.test(label.replace(/-/g, ""))) {
    if (label.length <= 7) return label.padEnd(40, "0").slice(0, 40);
  }
  const h = fnv1a(`sha:${label}`).toString(16).padStart(8, "0");
  return (h + SHA_PAD).slice(0, 40);
}

const SHA_TO_LABEL: Record<string, string> = {
  "0000000000000000000000000000000000000001": "gf-init-001",
  "73fb91d00000000000000000000000000000001": "73fb91d",
  r2def456000000000000000000000000000001: "r2-def456",
  "982af11000000000000000000000000000001": "982af11",
  r3a41c9e000000000000000000000000000001: "r3-a41c9e0",
};

export function shortSha(sha: string, len = 12): string {
  return SHA_TO_LABEL[sha] ?? sha.slice(0, len);
}

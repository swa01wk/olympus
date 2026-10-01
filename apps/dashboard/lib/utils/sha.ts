const SHA_TO_LABEL: Record<string, string> = {
  "0000000000000000000000000000000000000001": "gf-init-001",
  "73fb91d00000000000000000000000000000001": "73fb91d",
  r2def456000000000000000000000000000001: "r2-def456",
  "982af11000000000000000000000000000001": "982af11",
  r3a41c9e000000000000000000000000000001: "r3-a41c9e0",
};

/** 12-char display default used across Repository & Execution surfaces. */
export function formatShortSha(sha: string | null | undefined, len = 12): string {
  if (!sha) return "—";
  const labeled = SHA_TO_LABEL[sha];
  if (labeled) return labeled.length <= len ? labeled : labeled.slice(0, len);
  return sha.length <= len ? sha : sha.slice(0, len);
}

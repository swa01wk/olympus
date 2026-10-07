/** Best-effort map from record key prefix to lifecycle stage for EXPLAIN links. */
const PREFIX_TO_STAGE: Record<string, string> = {
  APR: "PRODUCT_MODEL",
  CL: "PRODUCT_MODEL",
  SPEC: "PRODUCT_MODEL",
  TASK: "DEVELOPMENT",
  TC: "PLANNING",
  IC: "INTEGRATION",
  EX: "DEVELOPMENT",
  REL: "RELEASE",
  DC: "DISCOVERY",
};

export function stageForRecordKey(key: string): string | undefined {
  const prefix = key.split("-")[0]?.toUpperCase();
  if (!prefix) return undefined;
  return PREFIX_TO_STAGE[prefix];
}

export type ExplainSegment =
  | { kind: "text"; value: string }
  | { kind: "record"; value: string; stage?: string };

const RECORD_PATTERN = /\b([A-Z]{2,}-\d+)\b/g;

export function splitExplainText(text: string): ExplainSegment[] {
  const segments: ExplainSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(RECORD_PATTERN)) {
    const index = match.index ?? 0;
    if (index > last) segments.push({ kind: "text", value: text.slice(last, index) });
    const value = match[1];
    segments.push({ kind: "record", value, stage: stageForRecordKey(value) });
    last = index + value.length;
  }
  if (last < text.length) segments.push({ kind: "text", value: text.slice(last) });
  if (segments.length === 0) segments.push({ kind: "text", value: text });
  return segments;
}

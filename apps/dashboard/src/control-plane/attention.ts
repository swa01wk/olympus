import { attentionPriority, mapBackendStatus } from "@/src/adapters/status";

export type AttentionItem = {
  id: string;
  headline: string;
  uiStatusKey: string;
  kind: string;
  recordRef?: string;
};

/** Merge inbox items; sort by design order unless server priority exists (G5). */
export function sortAttentionItems(items: AttentionItem[]): AttentionItem[] {
  return [...items].sort((a, b) => {
    const pa = attentionPriority(a.uiStatusKey);
    const pb = attentionPriority(b.uiStatusKey);
    if (pa !== pb) return pa - pb;
    return a.id.localeCompare(b.id);
  });
}

export function topAttentionItem(items: AttentionItem[]): AttentionItem | undefined {
  return sortAttentionItems(items)[0];
}

/** Map backend approval/clarification inbox row to attention item. */
export function attentionFromInboxRow(row: {
  kind: string;
  id: string;
  title: string;
  why?: string;
}): AttentionItem {
  const uiStatusKey =
    row.kind === "APPROVAL" ? "approval-pending" : row.kind === "CLARIFICATION" ? "checkpointed" : "pending";
  return {
    id: row.id,
    kind: row.kind,
    headline: row.why ?? row.title,
    uiStatusKey,
    recordRef: row.id,
  };
}

export function statusKeyForTaskBlocked(blockedReason: string | null | undefined): string {
  if (blockedReason) return "blocked";
  return mapBackendStatus("READY").uiKey;
}

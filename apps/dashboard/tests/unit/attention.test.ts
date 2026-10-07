import { describe, expect, it } from "vitest";
import {
  attentionFromInboxRow,
  sortAttentionItems,
  topAttentionItem,
} from "@/src/control-plane/attention";

describe("attention ordering", () => {
  it("prioritizes checkpointed over pending approval", () => {
    const items = sortAttentionItems([
      attentionFromInboxRow({ kind: "APPROVAL", id: "a1", title: "Scope", why: "Approve scope" }),
      attentionFromInboxRow({
        kind: "CLARIFICATION",
        id: "c1",
        title: "CL-1",
        why: "Which baseline?",
      }),
    ]);
    expect(items[0].kind).toBe("CLARIFICATION");
    expect(topAttentionItem(items)?.uiStatusKey).toBe("checkpointed");
  });
});

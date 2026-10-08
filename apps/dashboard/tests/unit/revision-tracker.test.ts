import { describe, expect, it } from "vitest";
import {
  parseRevisionCompleted,
  parseRevisionRequested,
  subjectMatchesFocus,
} from "@/lib/revision-tracker";

describe("revision-tracker", () => {
  it("matches focus by subject id when type omitted", () => {
    expect(
      subjectMatchesFocus(
        { subject_type: "architecture", subject_id: "a1" },
        "",
        "a1",
      ),
    ).toBe(true);
  });

  it("normalizes subject types for match", () => {
    expect(
      subjectMatchesFocus(
        { subject_type: "spec_delta", subject_id: "d1" },
        "SPEC_DELTA",
        "d1",
      ),
    ).toBe(true);
  });

  it("parses revision.requested payload", () => {
    const parsed = parseRevisionRequested({
      approval_id: "apr-1",
      subject_type: "architecture",
      subject_id: "arch-1",
      task_id: "task-1",
    });
    expect(parsed?.approvalId).toBe("apr-1");
  });

  it("parses revision.completed payload", () => {
    const parsed = parseRevisionCompleted({
      approval_id: "apr-1",
      old_subject_id: "old",
      new_subject_id: "new",
    });
    expect(parsed?.newSubjectId).toBe("new");
  });
});

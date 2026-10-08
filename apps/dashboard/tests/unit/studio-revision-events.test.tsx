import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StudioFocusProvider } from "@/lib/studio-focus";
import { StudioRevisionProvider, useStudioRevision } from "@/lib/studio-revision";
import type { ReactNode } from "react";

function wrap({ children }: { children: ReactNode }) {
  return (
    <StudioFocusProvider>
      <StudioRevisionProvider>{children}</StudioRevisionProvider>
    </StudioFocusProvider>
  );
}

describe("studio revision events", () => {
  it("tracks revising state for focused subject", () => {
    const { result } = renderHook(() => useStudioRevision(), { wrapper: wrap });
    act(() => {
      result.current.onDomainEvent(
        "revision.requested",
        {
          approval_id: "apr-1",
          subject_type: "architecture",
          subject_id: "arch-1",
          task_id: "task-1",
        },
        null,
      );
    });
    expect(result.current.revising).toBeNull();

    act(() => {
      result.current.onDomainEvent(
        "revision.requested",
        {
          approval_id: "apr-1",
          subject_type: "architecture",
          subject_id: "arch-1",
          task_id: "task-1",
        },
        { subject_type: "architecture", subject_id: "arch-1" },
      );
    });
    expect(result.current.revising?.taskId).toBe("task-1");
  });
});

import type { StudioFocus } from "@/lib/studio-focus";

export type RevisionRequestedState = {
  approvalId: string;
  subjectType: string;
  subjectId: string;
  taskId: string;
  nextVersion: number;
};

export type RevisionCompletedState = {
  approvalId: string;
  subjectType: string;
  oldSubjectId: string;
  newSubjectId: string;
};

export function normalizeSubjectType(subjectType: string): string {
  return subjectType.trim().toLowerCase().replace(/-/g, "_");
}

export function subjectMatchesFocus(
  focus: StudioFocus | null,
  subjectType: string,
  subjectId: string,
): boolean {
  if (!focus) return false;
  if (focus.subject_id !== subjectId) return false;
  if (!subjectType.trim()) return true;
  return normalizeSubjectType(focus.subject_type) === normalizeSubjectType(subjectType);
}

export function parseRevisionRequested(
  payload: Record<string, unknown>,
): Omit<RevisionRequestedState, "nextVersion"> | null {
  const approvalId = payload.approval_id;
  const subjectType = payload.subject_type;
  const subjectId = payload.subject_id;
  const taskId = payload.task_id;
  if (
    typeof approvalId !== "string" ||
    typeof subjectType !== "string" ||
    typeof subjectId !== "string" ||
    typeof taskId !== "string"
  ) {
    return null;
  }
  return { approvalId, subjectType, subjectId, taskId };
}

export function parseRevisionCompleted(
  payload: Record<string, unknown>,
): RevisionCompletedState | null {
  const approvalId = payload.approval_id;
  const oldSubjectId = payload.old_subject_id;
  const newSubjectId = payload.new_subject_id;
  const subjectType = payload.subject_type;
  if (
    typeof approvalId !== "string" ||
    typeof oldSubjectId !== "string" ||
    typeof newSubjectId !== "string"
  ) {
    return null;
  }
  return {
    approvalId,
    oldSubjectId,
    newSubjectId,
    subjectType: typeof subjectType === "string" ? subjectType : "",
  };
}

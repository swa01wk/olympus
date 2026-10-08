/** Parse reviewer feedback from approval audit rows (RL1: note may appear on audit `after`). */

export type AuditRow = {
  id: string;
  action: string;
  actor_id: string;
  before: unknown;
  after: unknown;
  occurred_at: string;
};

export type ChangesRequestedAuditView = {
  note: string | null;
  actorId: string;
  occurredAt: string;
};

export const REQUEST_CHANGES_INTERIM_HELPER =
  "Your note is recorded. The agent won't revise from it until revision support ships; to change this now, edit it (feature specs) or regenerate it.";

export function parseChangesRequestedAudit(rows: AuditRow[]): ChangesRequestedAuditView | null {
  const ordered = [...rows].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
  const changeRow =
    [...ordered].reverse().find((row) => {
      const after = row.after as Record<string, unknown> | null;
      if (after?.status === "CHANGES_REQUESTED") return true;
      if (after?.command === "request_changes") return true;
      return row.action.includes("request_changes");
    }) ?? null;

  if (!changeRow) return null;

  const after = changeRow.after as Record<string, unknown> | null;
  const note =
    (typeof after?.note === "string" && after.note.trim() ? after.note : null) ??
    (typeof after?.decision_note === "string" && after.decision_note.trim()
      ? after.decision_note
      : null);

  return {
    note,
    actorId: changeRow.actor_id,
    occurredAt: changeRow.occurred_at,
  };
}

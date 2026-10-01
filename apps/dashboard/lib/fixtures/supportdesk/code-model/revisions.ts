/** Declarative SupportDesk paths shared across index revisions (R1, R2, R3). */
export const SUPPORTDESK_TREE = [
  "app/main.py",
  "app/api/tickets.py",
  "app/services/ticket_service.py",
  "app/repositories/ticket_repository.py",
  "app/models/ticket.py",
  "app/schemas/ticket.py",
  "tests/test_create_ticket.py",
  "tests/test_ticket_status.py",
  "tests/test_priority.py",
] as const;

export type RevisionLabel = "R1" | "R2" | "R3-RC1" | "R3";

export function revisionExtraFiles(label: RevisionLabel): string[] {
  if (label === "R2" || label === "R3-RC1" || label === "R3") {
    return ["app/models/priority.py"];
  }
  return [];
}

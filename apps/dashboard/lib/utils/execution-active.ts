/** Execution counts as actively doing work (not just queued). */
const ACTIVE: Set<string> = new Set([
  "LEASED",
  "STARTED",
  "CHECKPOINTED",
  "OUTPUT_PRODUCED",
  "VALIDATING",
  "COMMITTED",
]);

export function isExecutionActive(status: string): boolean {
  return ACTIVE.has(status);
}

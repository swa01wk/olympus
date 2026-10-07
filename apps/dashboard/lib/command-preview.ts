export function previewReleaseApprove(releaseId: string, idempotencyKey: string): string {
  return `POST /releases/${releaseId}/approve · Idempotency-Key=${truncateKey(idempotencyKey)}`;
}

export function previewApprovalDecision(
  approvalId: string,
  decision: string,
  note: string,
  idempotencyKey: string,
): string {
  const noteHint = note.trim() ? " · note=…" : "";
  return `POST /approvals/${approvalId}/decision · decision=${decision}${noteHint} · Idempotency-Key=${truncateKey(idempotencyKey)}`;
}

export function previewClarificationAnswer(clarificationId: string, answer: string): string {
  return `POST /clarifications/${clarificationId}/answer · answer=${truncateText(answer, 48)}`;
}

export function previewCreateCycle(projectId: string, type: string, objective: string): string {
  return `POST /projects/${projectId}/delivery-cycles · type=${type} · objective=${truncateText(objective, 64)}`;
}

export function previewCycleCommand(
  cycleId: string,
  command: string,
  expectedState: string,
  idempotencyKey: string,
  payload?: Record<string, unknown> | null,
): string {
  const payloadHint =
    payload && Object.keys(payload).length > 0 ? ` · payload=${JSON.stringify(payload)}` : "";
  return `POST /delivery-cycles/${cycleId}/commands/${command} · expected_state=${expectedState}${payloadHint} · Idempotency-Key=${truncateKey(idempotencyKey)}`;
}

export function previewOrchestratorTurn(sessionId: string, message: string): string {
  return `POST /orchestrator/sessions/${sessionId}/turns · message=${truncateText(message, 64)}`;
}

export function previewStudioPost(
  path: string,
  body?: Record<string, unknown> | null,
  idempotencyKey?: string,
): string {
  return previewRunnableRoute(path, body ?? null, undefined, idempotencyKey);
}

export function previewRunnableRoute(
  path: string,
  body: Record<string, unknown> | null,
  query?: Record<string, string>,
  idempotencyKey?: string,
): string {
  const qs = query ? `?${new URLSearchParams(query)}` : "";
  const bodyHint =
    body && Object.keys(body).length > 0 ? ` · ${truncateText(JSON.stringify(body), 80)}` : "";
  const idem = idempotencyKey ? ` · Idempotency-Key=${truncateKey(idempotencyKey)}` : "";
  return `POST ${path}${qs}${bodyHint}${idem}`;
}

function truncateKey(key: string): string {
  return key.length > 12 ? `${key.slice(0, 12)}…` : key;
}

function truncateText(text: string, max: number): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

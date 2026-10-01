export class OlympusApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public reasons: string[] = [],
    public currentState?: string,
  ) {
    super(message);
    this.name = "OlympusApiError";
  }
}

export class CapabilityPendingError extends Error {
  constructor(
    public capabilityId: string,
    public backendPhase: string,
  ) {
    super(`Backend capability pending: ${capabilityId} (Phase ${backendPhase})`);
    this.name = "CapabilityPendingError";
  }
}

export async function normalizeResponseError(res: Response): Promise<never> {
  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    /* empty */
  }
  const reasons = Array.isArray(body.reasons)
    ? (body.reasons as string[])
    : [];
  const code =
    (body.code as string) ??
    (body.detail as string) ??
    res.statusText ??
    "UNKNOWN";
  const message = (body.message as string) ?? String(code);
  const current = body.current as string | undefined;
  throw new OlympusApiError(res.status, String(code), message, reasons, current);
}

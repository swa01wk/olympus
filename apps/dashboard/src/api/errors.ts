import type { ApiErrorBody } from "@/src/api/types/core";

export class OlympusApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "OlympusApiError";
    this.status = status;
    this.code = code;
    this.details = details ?? null;
  }
}

export async function errorFromResponse(res: Response): Promise<OlympusApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    body = {};
  }
  const code =
    typeof body.code === "string"
      ? body.code
      : res.status === 401
        ? "UNAUTHENTICATED"
        : res.status === 403
          ? "FORBIDDEN"
          : "HTTP_ERROR";
  const message =
    typeof body.message === "string"
      ? body.message
      : typeof body.detail === "string"
        ? body.detail
        : res.statusText || "Request failed";
  return new OlympusApiError(res.status, code, message, body.details ?? body.detail);
}

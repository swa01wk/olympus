import { getAccessToken, getApiBaseUrl } from "@/src/api/config";
import { errorFromResponse, OlympusApiError } from "@/src/api/errors";
import { newIdempotencyKey } from "@/lib/utils";

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  idempotencyKey?: string;
  token?: string | null;
  signal?: AbortSignal;
  headers?: Record<string, string>;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const base = getApiBaseUrl();
  const url = path.startsWith("http") ? path : `${base}${path.startsWith("/") ? "" : "/"}${path}`;
  const token = options.token !== undefined ? options.token : getAccessToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers,
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const method = options.method ?? "GET";
  let body: string | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (method !== "GET") {
    headers["Idempotency-Key"] = options.idempotencyKey ?? newIdempotencyKey();
  }
  const res = await fetch(url, { method, headers, body, signal: options.signal });
  if (!res.ok) throw await errorFromResponse(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export function isApiError(err: unknown): err is OlympusApiError {
  return err instanceof OlympusApiError;
}

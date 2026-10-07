const API_URL = process.env.NEXT_PUBLIC_OLYMPUS_API_URL ?? "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return API_URL.replace(/\/$/, "");
}

const TOKEN_STORAGE_KEY = "olympus_api_token";

/** Dev token from env; persisted token from login (Phase 6). */
export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return process.env.OLYMPUS_API_TOKEN ?? process.env.NEXT_PUBLIC_OLYMPUS_API_TOKEN ?? null;
  }
  return (
    window.localStorage.getItem(TOKEN_STORAGE_KEY) ??
    process.env.NEXT_PUBLIC_OLYMPUS_API_TOKEN ??
    null
  );
}

export function setAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

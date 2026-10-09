import { getAccessToken, getApiBaseUrl } from "@/src/api/config";
import type { DomainEventPayload } from "@/src/api/types/core";

export type StreamState = "connecting" | "live" | "disconnected";

export type CycleStreamHandlers = {
  onEvent?: (event: DomainEventPayload) => void;
  onStateChange?: (state: StreamState) => void;
  /** Updated whenever an SSE block includes an `id:` line (event sequence). */
  onLastEventId?: (sequence: string) => void;
};

export type ConnectCycleStreamOptions = {
  /** Sent as `Last-Event-ID` on this connection (SSE resume). */
  lastEventId?: string | null;
};

function parseSseBlock(block: string): { event: DomainEventPayload; lastEventId: string | null } | null {
  let eventType = "message";
  let data = "";
  let lastEventId: string | null = null;
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) eventType = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
    if (line.startsWith("id:")) lastEventId = line.slice(3).trim();
  }
  if (!data) return null;
  try {
    const parsed = JSON.parse(data) as DomainEventPayload;
    if (!parsed.event_type) parsed.event_type = eventType;
    if (lastEventId != null && lastEventId !== "") {
      const seq = Number(lastEventId);
      if (!Number.isNaN(seq)) parsed.sequence = seq;
    }
    return { event: parsed, lastEventId };
  } catch {
    return null;
  }
}

/** @internal Exported for unit tests. */
export function parseCycleSseBlock(block: string): DomainEventPayload | null {
  return parseSseBlock(block)?.event ?? null;
}

export function connectCycleEventStream(
  cycleId: string,
  handlers: CycleStreamHandlers,
  signal: AbortSignal,
  connectOptions: ConnectCycleStreamOptions = {},
): Promise<void> {
  return connectEventStream(
    `/delivery-cycles/${cycleId}/events/stream`,
    handlers,
    signal,
    connectOptions,
  );
}

/**
 * Fetch-based SSE so Authorization headers work (native EventSource cannot).
 */
export async function connectEventStream(
  path: string,
  handlers: CycleStreamHandlers,
  signal: AbortSignal,
  connectOptions: ConnectCycleStreamOptions = {},
): Promise<void> {
  const base = getApiBaseUrl();
  const token = getAccessToken();
  handlers.onStateChange?.("connecting");
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (connectOptions.lastEventId) {
    headers["Last-Event-ID"] = connectOptions.lastEventId;
  }

  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      headers,
      signal,
    });
  } catch {
    handlers.onStateChange?.("disconnected");
    return;
  }

  if (!res.ok || !res.body) {
    handlers.onStateChange?.("disconnected");
    return;
  }

  handlers.onStateChange?.("live");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (part.startsWith(":")) continue;
        const parsed = parseSseBlock(part);
        if (!parsed) continue;
        if (parsed.lastEventId) handlers.onLastEventId?.(parsed.lastEventId);
        handlers.onEvent?.(parsed.event);
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") handlers.onStateChange?.("disconnected");
    throw err;
  } finally {
    handlers.onStateChange?.("disconnected");
  }
}

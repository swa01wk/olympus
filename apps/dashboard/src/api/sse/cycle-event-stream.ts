import { getAccessToken, getApiBaseUrl } from "@/src/api/config";
import type { DomainEventPayload } from "@/src/api/types/core";

export type StreamState = "connecting" | "live" | "disconnected";

export type CycleStreamHandlers = {
  onEvent?: (event: DomainEventPayload) => void;
  onStateChange?: (state: StreamState) => void;
};

function parseSseBlock(block: string): DomainEventPayload | null {
  let eventType = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) eventType = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    const parsed = JSON.parse(data) as DomainEventPayload;
    if (!parsed.event_type) parsed.event_type = eventType;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Fetch-based SSE so Authorization headers work (native EventSource cannot).
 */
export async function connectCycleEventStream(
  cycleId: string,
  handlers: CycleStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const base = getApiBaseUrl();
  const token = getAccessToken();
  handlers.onStateChange?.("connecting");
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${base}/delivery-cycles/${cycleId}/events/stream`, {
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
        const evt = parseSseBlock(part);
        if (evt) handlers.onEvent?.(evt);
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") handlers.onStateChange?.("disconnected");
    throw err;
  } finally {
    handlers.onStateChange?.("disconnected");
  }
}

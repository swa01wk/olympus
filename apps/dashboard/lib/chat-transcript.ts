import type { OrchestratorTurn } from "@/src/api/types/orchestrator";

export function turnText(turn: OrchestratorTurn): string {
  return turn.text || turn.message || "";
}

/** Hide orchestrator system scheduling lines from the transcript (C3). */
export function isHiddenSystemTurn(turn: OrchestratorTurn): boolean {
  if (turn.role !== "system") return false;
  return /scheduled/i.test(turnText(turn));
}

export function visibleSessionTurns(turns: OrchestratorTurn[]): OrchestratorTurn[] {
  return turns.filter((t) => !isHiddenSystemTurn(t));
}

export function sessionStorageKey(cycleId: string): string {
  return `olympus.chat.${cycleId}`;
}

export type StoredChatSession = {
  sessionId: string;
  expiresAt: string;
};

export function readStoredSession(cycleId: string): StoredChatSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(sessionStorageKey(cycleId));
    if (!raw) return null;
    return JSON.parse(raw) as StoredChatSession;
  } catch {
    return null;
  }
}

export function writeStoredSession(cycleId: string, data: StoredChatSession): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(sessionStorageKey(cycleId), JSON.stringify(data));
}

export function clearStoredSession(cycleId: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(sessionStorageKey(cycleId));
}

export function isSessionExpired(expiresAt: string): boolean {
  return Date.parse(expiresAt) <= Date.now();
}

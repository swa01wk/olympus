"use client";

import {
  clearStoredSession,
  isSessionExpired,
  readStoredSession,
  turnText,
  visibleSessionTurns,
  writeStoredSession,
} from "@/lib/chat-transcript";
import { isApiError } from "@/src/api/client";
import { createOrchestratorSession, postOrchestratorTurn } from "@/src/api/commands";
import { fetchOrchestratorSession } from "@/src/api/resources";
import type { OrchestratorTurn } from "@/src/api/types/orchestrator";
import { useCallback, useEffect, useRef, useState } from "react";

export type ChatLine =
  | { kind: "user"; id: string; text: string }
  | { kind: "assistant"; id: string; turn: OrchestratorTurn }
  | { kind: "pending"; id: string; executionId: string }
  | { kind: "system-note"; id: string; text: string }
  | { kind: "pending-timeout"; id: string; executionId: string };

const POLL_MS = 2000;
const POLL_MAX_MS = 90000;

function linesFromTurns(turns: OrchestratorTurn[], systemNotes: ChatLine[]): ChatLine[] {
  const fromServer: ChatLine[] = visibleSessionTurns(turns).map((turn, i) => {
    const id = `turn-${i}-${turn.execution_id ?? i}`;
    if (turn.role === "user") {
      return { kind: "user", id, text: turnText(turn) };
    }
    return { kind: "assistant", id, turn };
  });
  return [...fromServer, ...systemNotes];
}

function systemNotesFromLines(prev: ChatLine[]): ChatLine[] {
  return prev.filter((l) => l.kind === "system-note");
}

export function useOrchestratorChat(projectId: string | undefined, cycleId: string | undefined) {
  const enabled = Boolean(projectId && cycleId);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pendingRef = useRef<Set<string>>(new Set());
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollStartedRef = useRef<number>(0);
  const turnCountAtSendRef = useRef<number>(0);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const applySession = useCallback((turns: OrchestratorTurn[]) => {
    setLines((prev) => linesFromTurns(turns, systemNotesFromLines(prev)));
  }, []);

  const syncFromSession = useCallback(
    async (sid: string) => {
      const session = await fetchOrchestratorSession(sid);
      if (cycleId) {
        writeStoredSession(cycleId, {
          sessionId: session.id,
          expiresAt: session.expires_at,
        });
      }
      applySession(session.turns);
      return session;
    },
    [applySession, cycleId],
  );

  const resolvePending = useCallback(
    async (executionId: string) => {
      if (!sessionId || !pendingRef.current.has(executionId)) return;
      pendingRef.current.delete(executionId);
      stopPolling();
      setLines((prev) => prev.filter((l) => l.kind !== "pending" || l.executionId !== executionId));
      try {
        await syncFromSession(sessionId);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not refresh session");
      }
    },
    [sessionId, stopPolling, syncFromSession],
  );

  const startPolling = useCallback(
    (executionId: string) => {
      stopPolling();
      pollStartedRef.current = Date.now();
      pollTimerRef.current = setInterval(() => {
        void (async () => {
          if (!sessionId) return;
          if (Date.now() - pollStartedRef.current > POLL_MAX_MS) {
            stopPolling();
            pendingRef.current.delete(executionId);
            setLines((prev) => [
              ...prev.filter((l) => l.kind !== "pending" || l.executionId !== executionId),
              { kind: "pending-timeout", id: `timeout-${executionId}`, executionId },
            ]);
            return;
          }
          try {
            const session = await fetchOrchestratorSession(sessionId);
            const visible = visibleSessionTurns(session.turns);
            if (visible.length > turnCountAtSendRef.current) {
              await resolvePending(executionId);
            }
          } catch {
            /* keep polling */
          }
        })();
      }, POLL_MS);
    },
    [resolvePending, sessionId, stopPolling],
  );

  const ensureSession = useCallback(async () => {
    if (!enabled || !projectId || !cycleId) return null;
    const stored = readStoredSession(cycleId);
    if (stored && !isSessionExpired(stored.expiresAt)) {
      try {
        const session = await fetchOrchestratorSession(stored.sessionId);
        setSessionId(session.id);
        applySession(session.turns);
        return session.id;
      } catch (e) {
        if (isApiError(e) && e.code === "NOT_FOUND") {
          clearStoredSession(cycleId);
        } else {
          throw e;
        }
      }
    } else if (stored) {
      clearStoredSession(cycleId);
    }
    const created = await createOrchestratorSession({
      project_id: projectId,
      delivery_cycle_id: cycleId,
    });
    writeStoredSession(cycleId, {
      sessionId: created.id,
      expiresAt: created.expires_at,
    });
    setSessionId(created.id);
    applySession(created.turns);
    return created.id;
  }, [applySession, cycleId, enabled, projectId]);

  useEffect(() => {
    if (!enabled) {
      stopPolling();
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        await ensureSession();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Session failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [enabled, ensureSession, stopPolling]);

  const onTurnCompleted = useCallback(
    (payload: Record<string, unknown>) => {
      const executionId = payload.execution_id;
      if (typeof executionId !== "string") return;
      void resolvePending(executionId);
    },
    [resolvePending],
  );

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || !enabled) return;
      setError(null);
      let sid = sessionId;
      if (!sid) sid = await ensureSession();
      if (!sid) return;

      setLines((prev) => [...prev, { kind: "user", id: `local-user-${Date.now()}`, text }]);

      try {
        const sessionBefore = await fetchOrchestratorSession(sid);
        turnCountAtSendRef.current = visibleSessionTurns(sessionBefore.turns).length;

        const { execution_id: executionId } = await postOrchestratorTurn(sid, text);
        pendingRef.current.add(executionId);
        setLines((prev) => [
          ...prev,
          { kind: "pending", id: `pending-${executionId}`, executionId },
        ]);
        startPolling(executionId);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Send failed");
      }
    },
    [enabled, ensureSession, sessionId, startPolling],
  );

  const addSystemNote = useCallback((text: string) => {
    const note: ChatLine = { kind: "system-note", id: `note-${Date.now()}`, text };
    setLines((prev) => [...prev, note]);
  }, []);

  return {
    sessionId,
    lines,
    loading,
    error,
    send,
    addSystemNote,
    onTurnCompleted,
    setError,
  };
}

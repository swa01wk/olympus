"use client";

import { DrawerPanel } from "@/components/dialogs/DrawerPanel";
import { Button } from "@/components/primitives";
import { previewOrchestratorTurn } from "@/lib/command-preview";
import { createOrchestratorSession, fetchOrchestratorSession, postOrchestratorTurn } from "@/src/api/resources";
import { useEffect, useState } from "react";

export function AskOlympusDrawer({
  open,
  onClose,
  projectId,
  cycleId,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string | null;
  cycleId: string | null;
}) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<{ role: string; text: string }[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !cycleId) return;
    let cancelled = false;
    (async () => {
      try {
        const session = await createOrchestratorSession({
          project_id: projectId,
          delivery_cycle_id: cycleId,
        });
        if (cancelled) return;
        setSessionId(session.id);
        setTurns(session.turns.map((t) => ({ role: t.role, text: t.text })));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not start session");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, projectId, cycleId]);

  const close = () => {
    setSessionId(null);
    setTurns([]);
    setMessage("");
    setError(null);
    onClose();
  };

  const send = async () => {
    if (!sessionId || !message.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await postOrchestratorTurn(sessionId, message.trim());
      const refreshed = await fetchOrchestratorSession(sessionId);
      setTurns(
        refreshed.turns.map((t) => ({
          role: t.role,
          text: t.text ?? t.message ?? JSON.stringify(t),
        })),
      );
      setMessage("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Turn failed");
    } finally {
      setBusy(false);
    }
  };

  const disabled = !cycleId;

  return (
    <DrawerPanel open={open} onClose={close} label="Orchestrator" title="Ask Olympus">
      {disabled && (
        <p className="text-sm ol-muted">
          Select a delivery cycle to converse. The orchestrator schedules agent work against that
          cycle.
        </p>
      )}
      {!disabled && (
        <>
          <div className="ol-ask-q flex flex-col gap-3 max-h-64 overflow-auto">
            {turns.map((t, i) => (
              <div key={i} className={t.role === "user" ? "ol-ask-q" : "ol-ask-a"}>
                <strong className="text-xs uppercase ol-muted">{t.role}</strong>
                <p>{t.text}</p>
              </div>
            ))}
            {!turns.length && <p className="text-sm ol-muted">Ask about cycle state, blockers, or next steps.</p>}
          </div>
          <label className="ol-field">
            <span className="ol-label">Message</span>
            <textarea
              rows={3}
              value={message}
              onChange={(ev) => setMessage(ev.target.value)}
              disabled={!sessionId || busy}
            />
          </label>
          {sessionId && message.trim() && (
            <code className="ol-cmd-api">{previewOrchestratorTurn(sessionId, message)}</code>
          )}
          <Button variant="primary" disabled={!sessionId || !message.trim() || busy} onClick={send}>
            Send
          </Button>
          {error && (
            <div className="ol-sent" role="alert">
              {error}
            </div>
          )}
        </>
      )}
    </DrawerPanel>
  );
}

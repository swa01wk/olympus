"use client";

import { Button, Panel } from "@/components/primitives";
import { previewCycleCommand } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { sendDeliveryCycleCommand } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import type { TransitionPreview } from "@/src/api/types/core";
import { useMemo, useState } from "react";

function isSecondaryCommand(command: string): boolean {
  return (
    command === "cancel" ||
    command === "return_to_development" ||
    command.startsWith("revise_")
  );
}

function pickPrimaryTransition(
  transitions: TransitionPreview[],
  cycleState: string,
): TransitionPreview | undefined {
  const forward = transitions.filter(
    (t) => t.to_state !== cycleState && !isSecondaryCommand(t.command),
  );
  return forward[0] ?? transitions.find((t) => !isSecondaryCommand(t.command));
}

function pickSecondaryTransitions(
  transitions: TransitionPreview[],
): TransitionPreview[] {
  return transitions.filter((t) => isSecondaryCommand(t.command));
}

export function NextStepBar({
  cycleId,
  cycleState,
  nextTransitions,
  onTransition,
}: {
  cycleId: string;
  cycleState: string;
  nextTransitions: TransitionPreview[];
  onTransition: () => void;
}) {
  const primary = useMemo(
    () => pickPrimaryTransition(nextTransitions, cycleState),
    [nextTransitions, cycleState],
  );
  const secondary = useMemo(() => pickSecondaryTransitions(nextTransitions), [nextTransitions]);

  const [menuOpen, setMenuOpen] = useState(false);
  const [armed, setArmed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idem] = useState(() => newIdempotencyKey());

  if (!primary) return null;

  const canAdvance = primary.allowed && !primary.authorization_denied;

  const run = async (t: TransitionPreview) => {
    if (t.command === "cancel") {
      const ok = window.confirm("Cancel this delivery cycle? This is a governed human action.");
      if (!ok) return;
    }
    setBusy(true);
    setError(null);
    try {
      await sendDeliveryCycleCommand(cycleId, t.command, cycleState, null, newIdempotencyKey());
      setArmed(null);
      setMenuOpen(false);
      onTransition();
    } catch (e) {
      setError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Command failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Next step" sub="Rendered from GET next-transitions" className="ol-next-step-bar">
      <ul className="ol-next-guards">
        {primary.guard_results.map((g) => (
          <li key={g.guard_id}>
            <span aria-hidden="true">{g.ok ? "✓" : "✕"}</span> {g.guard_id}
            {!g.ok && g.reasons.length > 0 && (
              <span className="ol-muted"> — {g.reasons.join("; ")}</span>
            )}
          </li>
        ))}
      </ul>
      {primary.authorization_denied && (
        <p className="ol-body-sm ol-muted">Authorization denied for this command.</p>
      )}
      {armed === primary.command ? (
        <>
          <pre className="ol-cmd-api">
            {previewCycleCommand(cycleId, primary.command, cycleState, idem)}
          </pre>
          <div className="ol-ws-action-row">
            <Button variant="primary" disabled={!canAdvance || busy} onClick={() => run(primary)}>
              Confirm {primary.command}
            </Button>
            <Button variant="quiet" onClick={() => setArmed(null)}>
              Cancel
            </Button>
          </div>
        </>
      ) : (
        <div className="ol-ws-action-row">
          <Button
            variant="primary"
            disabled={!canAdvance || busy}
            onClick={() => setArmed(primary.command)}
          >
            {primary.command} → {primary.to_state.replace(/_/g, " ")}
          </Button>
          {secondary.length > 0 && (
            <div className="ol-next-menu">
              <Button variant="quiet" onClick={() => setMenuOpen((o) => !o)}>
                More commands
              </Button>
              {menuOpen && (
                <ul className="ol-next-menu-list">
                  {secondary.map((t) => (
                    <li key={t.command}>
                      <button
                        type="button"
                        className="ol-ws-list-btn"
                        disabled={!t.allowed || t.authorization_denied || busy}
                        onClick={() => run(t)}
                      >
                        {t.command}
                        {!t.allowed && <span className="ol-muted"> (blocked)</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
      {error && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {error}
        </p>
      )}
    </Panel>
  );
}

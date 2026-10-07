"use client";

import { Button } from "@/components/primitives";
import { previewRunnableRoute } from "@/lib/command-preview";
import { routeForProposal, type ProposalRouteContext } from "@/src/api/proposal-routes";
import { executeRunnableProposal } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import type { OrchestratorProposal } from "@/src/api/types/orchestrator";
import { newIdempotencyKey } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";

export function ProposalCard({
  proposal,
  ctx,
  studioHref,
  onDismiss,
  onRan,
}: {
  proposal: OrchestratorProposal;
  ctx: ProposalRouteContext;
  studioHref: string;
  onDismiss: () => void;
  onRan?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const routed = routeForProposal(proposal, ctx);
  const idem = newIdempotencyKey();

  if ("notRunnable" in routed) {
    return (
      <div className="ol-chat-proposal ol-chat-proposal-blocked">
        <p className="ol-label">Not runnable from chat</p>
        <p className="ol-body-sm">{routed.notRunnable}</p>
        <Link href={studioHref} className="ol-chat-link">
          Open in workspace
        </Link>
      </div>
    );
  }

  const preview = previewRunnableRoute(routed.path, routed.body, routed.query, idem);

  const run = async () => {
    setBusy(true);
    setRunError(null);
    setResult(null);
    try {
      await executeRunnableProposal(routed, idem);
      setResult("Command completed.");
      onRan?.();
    } catch (e) {
      setRunError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ol-chat-proposal">
      <p className="ol-label">Proposed command</p>
      <p className="ol-body-sm">
        <strong>{proposal.command}</strong> · {proposal.target_ref}
      </p>
      <p className="ol-body-sm ol-muted">{proposal.rationale}</p>
      <pre className="ol-cmd-api">{preview}</pre>
      <div className="ol-chat-proposal-actions">
        <Button variant="primary" disabled={busy} onClick={run}>
          Run
        </Button>
        <Button variant="quiet" disabled={busy} onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
      {result && <p className="ol-body-sm ol-chat-ok">{result}</p>}
      {runError && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {runError}
        </p>
      )}
    </div>
  );
}

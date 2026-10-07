"use client";

import { ExceptionState } from "@/components/truth/ExceptionState";

/** G9: connector UNKNOWN — reconciliation required, no blind retry in UI. */
export function ReconciliationRequired({
  connectorName,
  message,
  externalRef,
}: {
  connectorName: string;
  message?: string;
  externalRef?: string | null;
}) {
  return (
    <ExceptionState
      status="review"
      statusLabel="Reconciliation required"
      reason={
        message ??
        `Connector “${connectorName}” reported an unknown outcome — external state may have changed.`
      }
      consequence="Use the provider correlation ID to reconcile before retrying any side effect. This UI does not offer a blind retry."
    >
      {externalRef && (
        <p className="text-xs font-mono ol-muted">
          External correlation: {externalRef}
        </p>
      )}
    </ExceptionState>
  );
}

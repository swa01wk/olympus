"use client";

import { Button, StatusBadge } from "@/components/primitives";
import type { ReactNode } from "react";

/**
 * Standard exceptional-state anatomy (design 06-truth-rules):
 * chip → reason → consequence → permitted next action.
 */
export function ExceptionState({
  status,
  statusLabel,
  reason,
  consequence,
  action,
  children,
}: {
  status: string;
  statusLabel?: string;
  reason: string;
  consequence?: string;
  action?: { label: string; onClick: () => void };
  children?: ReactNode;
}) {
  return (
    <div className="ol-exc" role="status">
      <StatusBadge status={status} label={statusLabel} />
      <p className="ol-exc-reason">{reason}</p>
      {consequence && <p className="ol-exc-cons ol-muted text-sm">{consequence}</p>}
      {children}
      {action && (
        <Button variant="primary" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

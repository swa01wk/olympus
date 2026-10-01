"use client";

import { Button } from "@/components/ui/button";

export function ConfirmCommandDialog({
  open,
  command,
  targetState,
  guardSummary,
  onConfirm,
  onCancel,
  loading,
}: {
  open: boolean;
  command: string;
  targetState: string;
  guardSummary?: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-cmd-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl">
        <h2 id="confirm-cmd-title" className="text-lg font-semibold">
          Confirm command
        </h2>
        <p className="mt-2 font-mono text-sm">
          {command} → {targetState}
        </p>
        {guardSummary && <p className="mt-2 text-xs text-[var(--muted)]">{guardSummary}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={loading}>
            Confirm
          </Button>
        </div>
      </div>
    </div>
  );
}

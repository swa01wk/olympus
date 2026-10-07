"use client";

import { ModalDialog } from "@/components/dialogs/ModalDialog";
import { Button, Label } from "@/components/primitives";
import { previewCycleCommand } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { sendDeliveryCycleCommand } from "@/src/api/commands";
import { queryKeys } from "@/src/api/query-keys";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export type CycleCommandRequest = {
  cycleId: string;
  command: string;
  expectedState: string;
  label: string;
  payload?: Record<string, unknown> | null;
};

export function CycleCommandDialog({
  open,
  request,
  onClose,
  onSuccess,
}: {
  open: boolean;
  request: CycleCommandRequest | null;
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const preview = request
    ? previewCycleCommand(
        request.cycleId,
        request.command,
        request.expectedState,
        "preview",
        request.payload,
      )
    : "";

  const confirm = async () => {
    if (!request) return;
    setBusy(true);
    setError(null);
    try {
      await sendDeliveryCycleCommand(
        request.cycleId,
        request.command,
        request.expectedState,
        request.payload ?? null,
        newIdempotencyKey(),
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.cycles.detail(request.cycleId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.cycles.overview(request.cycleId) });
      onSuccess?.();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Command rejected");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalDialog
      open={open && Boolean(request)}
      onClose={onClose}
      label="Permitted command"
      title={request?.label ?? "Confirm command"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={busy} onClick={confirm}>
            Send command
          </Button>
        </>
      }
    >
      {request && (
        <div className="ol-appr">
          <p className="text-sm">
            The server validates <strong>expected_state={request.expectedState}</strong>, your
            authorization, and guard predicates before transitioning the cycle.
          </p>
          <div>
            <Label>API preview</Label>
            <code className="ol-cmd-api">{preview}</code>
          </div>
          {error && (
            <div className="ol-sent" role="alert">
              {error}
            </div>
          )}
        </div>
      )}
    </ModalDialog>
  );
}

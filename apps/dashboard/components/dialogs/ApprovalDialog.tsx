"use client";

import { ModalDialog } from "@/components/dialogs/ModalDialog";
import { Button, Label } from "@/components/primitives";
import { previewApprovalDecision } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { sendApprovalDecision } from "@/src/api/commands";
import { fetchApproval } from "@/src/api/resources";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export function ApprovalDialog({
  open,
  approvalId,
  onClose,
  onSuccess,
}: {
  open: boolean;
  approvalId: string | null;
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const approval = useQuery({
    queryKey: ["approvals", "detail", approvalId ?? ""],
    queryFn: () => fetchApproval(approvalId!),
    enabled: open && Boolean(approvalId),
  });

  const a = approval.data;

  const decide = async (decision: "APPROVED" | "REJECTED" | "CHANGES_REQUESTED") => {
    if (!approvalId || !note.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const idem = newIdempotencyKey();
      await sendApprovalDecision(approvalId, decision, note.trim(), idem);
      await queryClient.invalidateQueries({ queryKey: ["views", "inbox"] });
      onSuccess?.();
      onClose();
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  };

  const preview = approvalId
    ? previewApprovalDecision(approvalId, "APPROVED", note, "preview")
    : "";

  return (
    <ModalDialog
      open={open && Boolean(approvalId)}
      onClose={onClose}
      label={a ? `Approval review · ${a.key}` : "Approval review"}
      title={a?.approval_type ?? "Approval"}
      wide
      footer={
        <>
          <Button disabled={!note.trim() || busy} onClick={() => decide("REJECTED")}>
            Reject
          </Button>
          <Button disabled={!note.trim() || busy} onClick={() => decide("CHANGES_REQUESTED")}>
            Request changes
          </Button>
          <Button
            variant="primary"
            disabled={!note.trim() || busy}
            onClick={() => decide("APPROVED")}
          >
            Approve
          </Button>
        </>
      }
    >
      {approval.isLoading && <p className="text-sm ol-muted">Loading approval…</p>}
      {a && (
        <div className="ol-appr">
          <div className="ol-appr-scope">
            <div>
              <Label>Decision type</Label>
              <div>{a.approval_type}</div>
            </div>
            <div>
              <Label>Subject</Label>
              <div className="ol-id">
                {a.subject_type} · {a.subject_id.slice(0, 8)}…
              </div>
            </div>
            <div>
              <Label>Exact version / hash</Label>
              <div className="ol-id">
                v{a.subject_version} · {a.subject_hash.slice(0, 16)}…
              </div>
            </div>
          </div>
          <label className="ol-field">
            <span className="ol-label">Rationale (required)</span>
            <textarea
              rows={3}
              value={note}
              onChange={(ev) => setNote(ev.target.value)}
              placeholder="Why you are approving, rejecting, or requesting changes."
            />
          </label>
          <code className="ol-cmd-api">{preview}</code>
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

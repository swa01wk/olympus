"use client";

import { ModalDialog } from "@/components/dialogs/ModalDialog";
import { Button } from "@/components/primitives";
import { previewClarificationAnswer } from "@/lib/command-preview";
import { answerClarificationCommand } from "@/src/api/commands";
import { fetchClarification } from "@/src/api/resources";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export function CheckpointDialog({
  open,
  clarificationId,
  onClose,
  onSuccess,
}: {
  open: boolean;
  clarificationId: string | null;
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const row = useQuery({
    queryKey: ["clarifications", "detail", clarificationId ?? ""],
    queryFn: () => fetchClarification(clarificationId!),
    enabled: open && Boolean(clarificationId),
  });

  const c = row.data;

  const submit = async () => {
    if (!clarificationId || !answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await answerClarificationCommand(clarificationId, answer.trim());
      await queryClient.invalidateQueries({ queryKey: ["views", "inbox"] });
      onSuccess?.();
      onClose();
      setAnswer("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Answer failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalDialog
      open={open && Boolean(clarificationId)}
      onClose={onClose}
      label={c ? `Clarification · ${c.key}` : "Clarification"}
      title="Answer to resume"
      wide
      footer={
        <>
          <Button onClick={onClose}>Not now</Button>
          <Button variant="primary" disabled={!answer.trim() || busy} onClick={submit}>
            Record answer
          </Button>
        </>
      }
    >
      {row.isLoading && <p className="text-sm ol-muted">Loading…</p>}
      {c && (
        <div className="ol-appr">
          <p className="ol-why-sum">{c.question}</p>
          <label className="ol-field">
            <span className="ol-label">Your answer</span>
            <textarea
              rows={3}
              value={answer}
              onChange={(ev) => setAnswer(ev.target.value)}
              placeholder="Durable decision text — may resume execution or replan."
            />
          </label>
          <code className="ol-cmd-api">{previewClarificationAnswer(c.id, answer)}</code>
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

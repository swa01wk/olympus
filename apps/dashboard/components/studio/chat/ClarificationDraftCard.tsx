"use client";

import { Button } from "@/components/primitives";
import { previewClarificationAnswer } from "@/lib/command-preview";
import { answerClarification } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import type { Clarification } from "@/src/api/types/product-model";
import type { OrchestratorClarificationDraft } from "@/src/api/types/orchestrator";
import { useState } from "react";

export function ClarificationDraftCard({
  draft,
  clarifications,
  onAnswered,
}: {
  draft: OrchestratorClarificationDraft;
  clarifications: Clarification[];
  onAnswered?: () => void;
}) {
  const [answer, setAnswer] = useState(draft.answer);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const row = clarifications.find((c) => c.id === draft.clarification_id);
  const question = row?.question ?? "Clarification";

  const send = async () => {
    if (!answer.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await answerClarification(draft.clarification_id, answer.trim());
      onAnswered?.();
    } catch (e) {
      setErr(isApiError(e) ? e.message : "Answer failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ol-chat-clarification">
      <p className="ol-label">Clarification draft</p>
      <p className="ol-body-sm">{question}</p>
      <label className="ol-field">
        <span className="ol-label">Answer</span>
        <textarea rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={busy} />
      </label>
      <code className="ol-cmd-api">
        {previewClarificationAnswer(draft.clarification_id, answer)}
      </code>
      <Button variant="primary" disabled={busy || !answer.trim()} onClick={send}>
        Send answer
      </Button>
      {err && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {err}
        </p>
      )}
    </div>
  );
}

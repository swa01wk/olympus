"use client";

import { ChatTurnView } from "@/components/studio/chat/ChatTurnView";
import { Button } from "@/components/primitives";
import { previewOrchestratorTurn } from "@/lib/command-preview";
import { uploadProductSource } from "@/src/api/commands";
import { listSources } from "@/src/api/resources";
import { useStudioFocus } from "@/lib/studio-focus";
import { useOrchestratorChat } from "@/src/api/hooks/use-orchestrator-chat";
import { useClarifications } from "@/src/api/hooks/use-studio-queries";
import type { DeliveryCycle } from "@/src/api/types/core";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const PRD_ACCEPT = ".md,.txt,.pdf,text/markdown,text/plain,application/pdf";

export function ChatPanel({
  projectId,
  cycle,
  onTurnCompleted,
  onSelectStage,
  compact,
}: {
  projectId: string;
  cycle: DeliveryCycle;
  onTurnCompleted: (handler: (payload: Record<string, unknown>) => void) => void;
  onSelectStage: (stage: string) => void;
  compact?: boolean;
}) {
  const cycleId = cycle.id;
  const cycleState = cycle.state;
  const focus = useStudioFocus();
  const chat = useOrchestratorChat(projectId, cycleId, focus);
  const clarifications = useClarifications(projectId, "OPEN");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const fileRef = useRef<HTMLInputElement>(null);

  const proposalCtx = useMemo(
    () => ({ projectId, cycleId, cycleState }),
    [projectId, cycleId, cycleState],
  );

  const studioBase = `/projects/${projectId}/cycles/${cycleId}/studio`;

  useEffect(() => {
    onTurnCompleted(chat.onTurnCompleted);
  }, [chat.onTurnCompleted, onTurnCompleted]);

  const canAttachPrd = cycleState === "DISCOVERY" || cycleState === "PRODUCT_MODEL";

  const send = async () => {
    if (!message.trim()) return;
    setBusy(true);
    await chat.send(message);
    setMessage("");
    setBusy(false);
  };

  const onAttach = async (file: File) => {
    if (!canAttachPrd) return;
    setBusy(true);
    chat.setError(null);
    try {
      await uploadProductSource(projectId, cycleId, { file });
      const sources = await listSources(projectId);
      const latest = sources.reduce(
        (best, s) => (s.version > (best?.version ?? 0) ? s : best),
        sources[0],
      );
      const ver = latest?.version ?? "?";
      chat.addSystemNote(`PRD v${ver} ingested — open in workspace`);
      onSelectStage(cycleState === "DISCOVERY" ? "DISCOVERY" : "PRODUCT_MODEL");
    } catch (e) {
      chat.setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const dismissProposal = useCallback((key: string) => {
    setDismissed((prev) => new Set(prev).add(key));
  }, []);

  if (!cycleId) {
    return (
      <p className="ol-body ol-muted">
        Select a delivery cycle to converse. The orchestrator requires a cycle context.
      </p>
    );
  }

  return (
    <div className={compact ? "ol-chat ol-chat-compact" : "ol-chat"}>
      <div className="ol-chat-transcript" role="log" aria-live="polite">
        {chat.loading && <p className="ol-muted ol-body-sm">Connecting session…</p>}
        {chat.lines.map((line) => {
          if (line.kind === "user") {
            return (
              <div key={line.id} className="ol-chat-bubble ol-chat-user">
                <span className="ol-label">You</span>
                <p className="ol-body">{line.text}</p>
              </div>
            );
          }
          if (line.kind === "system-note") {
            return (
              <div key={line.id} className="ol-chat-bubble ol-chat-system">
                <p className="ol-body-sm">{line.text}</p>
              </div>
            );
          }
          if (line.kind === "pending") {
            return (
              <div key={line.id} className="ol-chat-bubble ol-chat-pending" aria-busy="true">
                <span className="ol-label">Assistant</span>
                <p className="ol-body-sm ol-muted">Working…</p>
              </div>
            );
          }
          if (line.kind === "pending-timeout") {
            return (
              <div key={line.id} className="ol-chat-bubble ol-chat-pending">
                <p className="ol-body-sm">
                  Still working — the execution is{" "}
                  <a href={`/executions/${line.executionId}`} className="ol-chat-link">
                    {line.executionId}
                  </a>
                </p>
              </div>
            );
          }
          if (line.kind !== "assistant") return null;
          const proposalKey = line.turn.proposal
            ? `${line.turn.proposal.command}:${line.turn.proposal.target_ref}`
            : "";
          return (
            <div key={line.id} className="ol-chat-bubble ol-chat-assistant">
              <span className="ol-label">Olympus</span>
              <ChatTurnView
                turn={line.turn}
                ctx={proposalCtx}
                studioBasePath={studioBase}
                clarifications={clarifications.data ?? []}
                dismissedProposalKey={dismissed.has(proposalKey) ? proposalKey : undefined}
                onDismissProposal={dismissProposal}
                onSelectStage={onSelectStage}
              />
            </div>
          );
        })}
        {!chat.lines.length && !chat.loading && (
          <p className="ol-body-sm ol-muted">Ask about cycle state, blockers, or next steps.</p>
        )}
      </div>

      <div className="ol-chat-composer">
        <label className="ol-field">
          <span className="ol-label">Message</span>
          <textarea
            rows={compact ? 2 : 3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={!chat.sessionId || busy || chat.loading}
          />
        </label>
        {chat.sessionId && message.trim() && (
          <code className="ol-cmd-api">{previewOrchestratorTurn(chat.sessionId, message)}</code>
        )}
        <div className="ol-chat-composer-actions">
          <input
            ref={fileRef}
            type="file"
            accept={PRD_ACCEPT}
            className="ol-visually-hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onAttach(f);
              e.target.value = "";
            }}
          />
          <Button
            variant="quiet"
            disabled={!canAttachPrd || busy || chat.loading}
            onClick={() => fileRef.current?.click()}
            title={
              canAttachPrd
                ? "Upload PRD (.md, .txt, .pdf)"
                : "PRD attach is only available in Discovery or Product model"
            }
          >
            Attach PRD
          </Button>
          <Button
            variant="primary"
            disabled={!chat.sessionId || !message.trim() || busy || chat.loading}
            onClick={send}
          >
            Send
          </Button>
        </div>
        {chat.error && (
          <div className="ol-sent" role="alert">
            {chat.error}
          </div>
        )}
      </div>
    </div>
  );
}

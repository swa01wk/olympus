"use client";

import { turnText } from "@/lib/chat-transcript";
import { useOrchestratorChat } from "@/src/api/hooks/use-orchestrator-chat";
import { useEffect, useRef, useState } from "react";

const SUGGESTIONS = ["What is happening right now?", "Why did this step stop?", "What happens next?"];

export function RunChat({
  projectId,
  cycleId,
  registerTurnHandler,
}: {
  projectId: string;
  cycleId: string;
  /** The run view forwards `orchestrator.turn_completed` stream events to this handler. */
  registerTurnHandler: (handler: (payload: Record<string, unknown>) => void) => void;
}) {
  const chat = useOrchestratorChat(projectId, cycleId, null);
  const [message, setMessage] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    registerTurnHandler(chat.onTurnCompleted);
  }, [chat.onTurnCompleted, registerTurnHandler]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [chat.lines.length]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessage("");
    await chat.send(trimmed);
  };

  return (
    <aside className="sp-card sp-chat" aria-label="Ask Olympus">
      <div className="sp-chat-head">
        <h2 className="sp-h2" style={{ marginBottom: 2 }}>
          Ask Olympus
        </h2>
        <p className="sp-small sp-muted" style={{ margin: 0 }}>
          Questions about this run. Each message uses your model budget.
        </p>
      </div>
      <div className="sp-chat-log" ref={logRef}>
        {chat.lines.length === 0 && (
          <div className="sp-stack" style={{ gap: 6, paddingBottom: 12 }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="sp-btn sp-suggestion" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        {chat.lines.map((line) => {
          if (line.kind === "user") {
            return (
              <div key={line.id} className="sp-bubble sp-bubble-user">
                {line.text}
              </div>
            );
          }
          if (line.kind === "assistant") {
            return (
              <div key={line.id} className="sp-bubble sp-bubble-bot">
                {turnText(line.turn)}
              </div>
            );
          }
          if (line.kind === "pending") {
            return (
              <div key={line.id} className="sp-bubble sp-bubble-bot sp-muted">
                Thinking…
              </div>
            );
          }
          if (line.kind === "pending-timeout") {
            return (
              <div key={line.id} className="sp-bubble sp-bubble-bot sp-muted">
                No reply yet. Is the worker running?
              </div>
            );
          }
          return (
            <div key={line.id} className="sp-small sp-muted">
              {line.text}
            </div>
          );
        })}
        {chat.error && (
          <p className="sp-error" role="alert">
            {chat.error}
          </p>
        )}
      </div>
      <form
        className="sp-chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          void send(message);
        }}
      >
        <input
          className="sp-input"
          value={message}
          placeholder="Ask a question…"
          aria-label="Message"
          onChange={(e) => setMessage(e.target.value)}
        />
        <button type="submit" className="sp-btn" disabled={!message.trim()}>
          Send
        </button>
      </form>
    </aside>
  );
}

"use client";

import { ApprovalSubject } from "@/components/simple/ApprovalSubject";
import { newIdempotencyKey } from "@/lib/utils";
import { isApiError } from "@/src/api/client";
import { answerClarification, sendApprovalDecision } from "@/src/api/commands";
import type { InboxItem } from "@/src/api/types/core";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

const TITLES: Record<string, string> = {
  SCOPE: "Are these the right features?",
  ARCHITECTURE: "Does this design look right?",
  ARCHITECTURE_DELTA: "Does this design change look right?",
  IMPLEMENTATION_SPEC: "Does this plan for the feature look right?",
  SPEC_DELTA: "Is this the change you want?",
  TASK_PLAN: "Ready to start coding with this task list?",
  EXPECTED_BEHAVIOR: "Is this how the app should behave?",
  UNREPRODUCED_REPAIR: "Fix a bug that could not be reproduced?",
  FINDING_WAIVER: "Accept this known issue?",
  ACTION: "Allow this action?",
  RELEASE: "Ready to release?",
};

type Decision = "APPROVED" | "CHANGES_REQUESTED" | "REJECTED";

function errorText(e: unknown): string {
  if (isApiError(e)) return e.message;
  return e instanceof Error ? e.message : "Something went wrong";
}

export function NeedsYou({
  items,
  projectId,
  inspectHref,
}: {
  items: InboxItem[];
  projectId: string;
  inspectHref: string;
}) {
  const questions = items.filter((i) => i.clarification && i.clarification.status === "OPEN");
  const approvals = items.filter((i) => i.approval && i.approval.status === "PENDING");
  if (questions.length === 0 && approvals.length === 0) return null;
  return (
    <section className="sp-stack" aria-label="Needs you">
      {questions.map((q) => (
        <QuestionCard key={q.id} item={q} />
      ))}
      {approvals.map((a) => (
        <ApprovalCard key={a.id} item={a} projectId={projectId} inspectHref={inspectHref} />
      ))}
    </section>
  );
}

function useRefreshRun() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["views", "inbox"] });
    void qc.invalidateQueries({ queryKey: ["autopilot"] });
    void qc.invalidateQueries({ queryKey: ["home"] });
  };
}

export function ApprovalCard({
  item,
  projectId,
  inspectHref,
}: {
  item: InboxItem;
  projectId: string;
  inspectHref: string;
}) {
  const approval = item.approval!;
  const refresh = useRefreshRun();
  const [mode, setMode] = useState<"idle" | "CHANGES_REQUESTED" | "REJECTED">("idle");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (decision: Decision) => {
    if (decision !== "APPROVED" && !note.trim()) {
      setError("Tell Olympus what to change, so the next version gets it right.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await sendApprovalDecision(
        approval.id,
        decision,
        decision === "APPROVED" ? null : note.trim(),
        newIdempotencyKey(),
      );
      refresh();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <article className="sp-card sp-needs">
      <h3 className="sp-needs-title">{TITLES[approval.approval_type] ?? item.title}</h3>
      <ApprovalSubject
        approvalType={approval.approval_type}
        subjectId={approval.subject_id}
        projectId={projectId}
      />
      {mode !== "idle" && (
        <div className="sp-field" style={{ marginBottom: 12 }}>
          <label className="sp-label" htmlFor={`note-${approval.id}`}>
            {mode === "CHANGES_REQUESTED" ? "What should change?" : "Why reject it?"}
          </label>
          <textarea
            id={`note-${approval.id}`}
            className="sp-textarea"
            value={note}
            autoFocus
            onChange={(e) => setNote(e.target.value)}
            placeholder={
              mode === "CHANGES_REQUESTED"
                ? "e.g. Use PostgreSQL instead of SQLite, and drop the admin dashboard."
                : "e.g. This isn't what I asked for."
            }
          />
        </div>
      )}
      {error && (
        <p className="sp-error" role="alert" style={{ marginBottom: 12 }}>
          {error}
        </p>
      )}
      <div className="sp-row">
        {mode === "idle" ? (
          <>
            <button
              type="button"
              className="sp-btn sp-btn-primary"
              disabled={busy}
              onClick={() => decide("APPROVED")}
            >
              {approval.approval_type === "RELEASE" ? "Release it" : "Approve"}
            </button>
            <button
              type="button"
              className="sp-btn"
              disabled={busy}
              onClick={() => setMode("CHANGES_REQUESTED")}
            >
              Request changes
            </button>
            <button
              type="button"
              className="sp-btn sp-btn-ghost sp-btn-danger"
              disabled={busy}
              onClick={() => setMode("REJECTED")}
            >
              Reject
            </button>
            <span className="sp-top-spacer" />
            <Link href={inspectHref} className="sp-small sp-muted">
              Full details
            </Link>
          </>
        ) : (
          <>
            <button
              type="button"
              className={mode === "REJECTED" ? "sp-btn sp-btn-danger" : "sp-btn sp-btn-primary"}
              disabled={busy}
              onClick={() => decide(mode)}
            >
              {mode === "CHANGES_REQUESTED" ? "Send feedback" : "Reject"}
            </button>
            <button
              type="button"
              className="sp-btn sp-btn-ghost"
              disabled={busy}
              onClick={() => {
                setMode("idle");
                setError(null);
              }}
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </article>
  );
}

export function QuestionCard({ item }: { item: InboxItem }) {
  const question = item.clarification!;
  const refresh = useRefreshRun();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    if (!answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await answerClarification(question.id, answer.trim());
      refresh();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <article className="sp-card sp-needs">
      <h3 className="sp-needs-title">Olympus has a question</h3>
      <p style={{ marginTop: 0, lineHeight: 1.5 }}>{question.question}</p>
      <div className="sp-field">
        <label className="sp-label" htmlFor={`answer-${question.id}`}>
          Your answer
        </label>
        <textarea
          id={`answer-${question.id}`}
          className="sp-textarea"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
      </div>
      {error && (
        <p className="sp-error" role="alert">
          {error}
        </p>
      )}
      <div className="sp-row" style={{ marginTop: 12 }}>
        <button
          type="button"
          className="sp-btn sp-btn-primary"
          disabled={busy || !answer.trim()}
          onClick={() => void send()}
        >
          Send answer
        </button>
      </div>
    </article>
  );
}

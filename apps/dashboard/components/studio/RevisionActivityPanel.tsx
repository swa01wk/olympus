"use client";

import { Panel } from "@/components/primitives";
import { diffJsonBodies, type DiffLine } from "@/lib/json-line-diff";
import { revisingAgentLabel } from "@/lib/revision-agents";
import { fetchRevisionSubjectBody } from "@/lib/revision-subject-body";
import { useStudioFocus } from "@/lib/studio-focus";
import { useStudioRevision } from "@/lib/studio-revision";
import { useApprovalDetail } from "@/src/api/hooks/use-studio-queries";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

function DiffView({ lines }: { lines: DiffLine[] }) {
  return (
    <pre className="ol-ws-pre ol-revision-diff" aria-label="Revision diff">
      {lines.map((line, i) => (
        <div
          key={`${i}-${line.kind}`}
          className={
            line.kind === "add"
              ? "ol-diff-add"
              : line.kind === "remove"
                ? "ol-diff-remove"
                : "ol-diff-same"
          }
        >
          {line.kind === "add" ? "+ " : line.kind === "remove" ? "- " : "  "}
          {line.text}
        </div>
      ))}
    </pre>
  );
}

export function RevisionActivityPanel() {
  const focus = useStudioFocus();
  const { revising, completed, clearCompleted } = useStudioRevision();

  const diffQuery = useQuery({
    queryKey: [
      "revision-diff",
      completed?.oldSubjectId,
      completed?.newSubjectId,
      completed?.subjectType,
    ],
    queryFn: async () => {
      if (!completed) return null;
      const subjectType = completed.subjectType || focus?.subject_type || "architecture";
      const [beforeBody, afterBody] = await Promise.all([
        fetchRevisionSubjectBody(subjectType, completed.oldSubjectId),
        fetchRevisionSubjectBody(subjectType, completed.newSubjectId),
      ]);
      return diffJsonBodies(beforeBody, afterBody);
    },
    enabled: Boolean(completed),
  });

  const approval = useApprovalDetail(revising?.approvalId);
  const nextVersion = (approval.data?.subject_version ?? 0) + 1;

  const agent = useMemo(
    () => revisingAgentLabel(revising?.subjectType ?? focus?.subject_type ?? ""),
    [revising?.subjectType, focus?.subject_type],
  );

  if (!revising && !completed) return null;

  return (
    <Panel
      title={completed ? "Revision complete" : "Revision in progress"}
      sub={completed ? "Compare prior and new versions" : undefined}
      className="ol-revision-activity"
    >
      {revising && (
        <p className="ol-body-sm" role="status">
          Revising: {agent} is preparing version {nextVersion > 0 ? nextVersion : "…"}
        </p>
      )}
      {completed && (
        <>
          {diffQuery.isLoading && <p className="ol-body-sm ol-muted">Loading diff…</p>}
          {diffQuery.isError && (
            <p className="ol-body-sm ol-chat-err">Could not load revision bodies for diff.</p>
          )}
          {diffQuery.data && <DiffView lines={diffQuery.data} />}
          <p className="ol-body-sm ol-muted">
            A fresh approval should appear in the Decision panel when the subject is ready.
          </p>
          <button type="button" className="ol-ws-list-btn" onClick={() => clearCompleted()}>
            Dismiss diff
          </button>
        </>
      )}
    </Panel>
  );
}

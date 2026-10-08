"use client";

import { Button, Label, Panel, Sha } from "@/components/primitives";
import {
  findPendingApprovalForStage,
  guardResultsForApprovalType,
} from "@/lib/studio-spine";
import { requestChangesHelperText } from "@/lib/request-changes-helper";
import { useStudioDecisionNoteOptional } from "@/lib/studio-decision-note";
import {
  previewApprovalDecision,
  previewReleaseApprove,
} from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { approveRelease, sendApprovalDecision } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import { useActorMe } from "@/src/api/hooks/use-olympus-queries";
import {
  useApprovalDetail,
  useFeatureSpecDetail,
  useProjectArchitecture,
  useReleaseManifest,
} from "@/src/api/hooks/use-studio-queries";
import { fetchAuditForTarget } from "@/src/api/resources";
import type { InboxItem, TransitionPreview } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

function decisionErrorMessage(err: unknown): { message: string; stale?: boolean } {
  if (isApiError(err)) {
    if (err.status === 403) {
      return { message: "You need the APPROVER role to decide this." };
    }
    const msg = err.message.toLowerCase();
    if (
      err.code.includes("SUBJECT") ||
      err.code.includes("HASH") ||
      err.code.includes("STALE") ||
      msg.includes("hash") ||
      msg.includes("version") ||
      msg.includes("changed")
    ) {
      return {
        message:
          "This changed after approval was requested. Request approval again from the stage actions.",
        stale: true,
      };
    }
    return { message: err.message };
  }
  return { message: err instanceof Error ? err.message : "Decision failed" };
}

function ApprovalSubjectPreview({
  approvalType,
  subjectType,
  subjectId,
  projectId,
}: {
  approvalType: string;
  subjectType: string;
  subjectId: string;
  projectId: string;
}) {
  const isArch = approvalType === "ARCHITECTURE" || approvalType === "ARCHITECTURE_DELTA";
  const isRelease = approvalType === "RELEASE" || approvalType === "DEPLOYMENT";
  const isSpec =
    subjectType.toLowerCase().includes("spec") || approvalType === "SCOPE" || approvalType.includes("SPEC");

  const architecture = useProjectArchitecture(isArch ? projectId : undefined);
  const spec = useFeatureSpecDetail(isSpec ? subjectId : undefined);
  const manifest = useReleaseManifest(isRelease ? subjectId : undefined);

  if (isArch && architecture.data) {
    return (
      <pre className="ol-ws-pre ol-body-sm">{JSON.stringify(architecture.data.body, null, 2)}</pre>
    );
  }
  if (isSpec && spec.data) {
    return (
      <div className="ol-body-sm">
        <p>{spec.data.body.summary}</p>
        <p className="ol-muted">{spec.data.body.behavior}</p>
      </div>
    );
  }
  if (isRelease && manifest.data) {
    return (
      <p className="ol-body-sm">
        Manifest hash <Sha value={manifest.data.content_hash} />
      </p>
    );
  }
  return (
    <p className="ol-body-sm ol-muted">
      {subjectType} · <span className="ol-id">{subjectId}</span>
    </p>
  );
}

export function DecisionPanel({
  stage,
  cycleType,
  inbox,
  projectId,
  nextTransitions,
  onDecided,
}: {
  stage: string;
  cycleType: DeliveryCycleType;
  inbox: InboxItem[];
  projectId: string;
  nextTransitions: TransitionPreview[];
  onDecided: () => void;
}) {
  const pending = findPendingApprovalForStage(inbox, stage, cycleType);
  const actor = useActorMe();
  const canDecide = (actor.data?.roles ?? []).includes("APPROVER");

  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const panelRef = useRef<HTMLElement | null>(null);
  const decisionNote = useStudioDecisionNoteOptional();

  const approval = useApprovalDetail(pending?.id);
  const a = approval.data;
  const guards = useMemo(
    () => (pending ? guardResultsForApprovalType(pending.approval_type, nextTransitions) : []),
    [pending, nextTransitions],
  );

  const audit = useQuery({
    queryKey: ["audit", "approval", pending?.id ?? ""],
    queryFn: () => fetchAuditForTarget("approval", pending!.id),
    enabled: Boolean(pending?.id),
  });

  useEffect(() => {
    decisionNote?.registerDecisionPanel(panelRef.current);
  });

  useEffect(() => {
    if (!pending || !decisionNote) return;
    const draft = decisionNote.consumePendingNote(pending.id);
    if (draft) setNote(draft);
  }, [decisionNote, pending?.id]);

  if (!pending) return null;

  const idem = newIdempotencyKey();
  const isRelease = pending.approval_type === "RELEASE" || pending.approval_type === "DEPLOYMENT";
  const previewApprove = isRelease
    ? previewReleaseApprove(pending.subject_id, idem)
    : previewApprovalDecision(pending.id, "APPROVED", note, idem);

  const decide = async (decision: "APPROVED" | "REJECTED" | "CHANGES_REQUESTED") => {
    if (!canDecide) return;
    if (decision !== "APPROVED" && !note.trim()) return;
    setBusy(true);
    setError(null);
    setStale(false);
    try {
      const key = newIdempotencyKey();
      if (decision === "APPROVED" && isRelease) {
        await approveRelease(pending.subject_id, key);
      } else {
        await sendApprovalDecision(
          pending.id,
          decision,
          decision === "APPROVED" ? note.trim() || null : note.trim(),
          key,
        );
      }
      setNote("");
      onDecided();
    } catch (e) {
      const mapped = decisionErrorMessage(e);
      setError(mapped.message);
      setStale(Boolean(mapped.stale));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div ref={panelRef}>
    <Panel
      title="Decision required"
      sub={`${pending.approval_type} · ${pending.key}`}
      className="ol-decision-panel"
    >
      <div className="ol-appr-scope">
        <div>
          <Label>Approval type</Label>
          <div>{pending.approval_type}</div>
        </div>
        <div>
          <Label>Subject</Label>
          <div className="ol-id">
            {pending.subject_type} · {pending.subject_id}
          </div>
        </div>
        <div>
          <Label>Subject hash</Label>
          <Sha value={pending.subject_hash} />
        </div>
        {a && (
          <div>
            <Label>Version</Label>
            <div>v{a.subject_version}</div>
          </div>
        )}
      </div>
      {guards.length > 0 && (
        <div className="ol-decision-guards">
          <p className="ol-label">Unlocks when satisfied</p>
          <ul className="ol-ws-bullets">
            {guards.map((g) => (
              <li key={g.guard_id}>
                {g.ok ? "✓" : "✕"} {g.guard_id}
                {!g.ok && g.reasons.length > 0 && (
                  <span className="ol-muted"> — {g.reasons.join("; ")}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <ApprovalSubjectPreview
        approvalType={pending.approval_type}
        subjectType={pending.subject_type}
        subjectId={pending.subject_id}
        projectId={projectId}
      />
      {!canDecide && (
        <p className="ol-body-sm ol-muted" role="status">
          You need the APPROVER role to decide this approval.
        </p>
      )}
      <label className="ol-field">
        <span className="ol-label">Note (required for Reject and Request changes)</span>
        <textarea
          rows={3}
          value={note}
          disabled={!canDecide || busy}
          onChange={(ev) => setNote(ev.target.value)}
          placeholder="Rationale for reject or request changes; optional for Approve."
        />
      </label>
      <code className="ol-cmd-api">{previewApprove}</code>
      <div className="ol-ws-action-row">
        <Button disabled={!canDecide || !note.trim() || busy} onClick={() => decide("REJECTED")}>
          Reject
        </Button>
        <Button
          disabled={!canDecide || !note.trim() || busy}
          onClick={() => decide("CHANGES_REQUESTED")}
        >
          Request changes
        </Button>
        <Button variant="primary" disabled={!canDecide || busy} onClick={() => decide("APPROVED")}>
          Approve
        </Button>
      </div>
      <p className="ol-body-sm ol-muted">{requestChangesHelperText(pending.approval_type)}</p>
      {error && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {error}
        </p>
      )}
      {stale && (
        <p className="ol-body-sm ol-muted">Re-run the stage request action after updating the subject.</p>
      )}
      {(audit.data ?? []).length > 0 && (
        <details className="ol-decision-history">
          <summary className="ol-label">Approval history</summary>
          <ul className="ol-ws-bullets">
            {audit.data!.map((row) => (
              <li key={row.id}>
                {row.occurred_at} · {row.action}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Panel>
    </div>
  );
}

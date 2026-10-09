"use client";

import { Button, EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import {
  mayProceedUnreproduced,
  mayRejectDefect,
  policyAllowsUnreproduced,
} from "@/lib/defect-reproduction";
import { previewStudioPost } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { proceedUnreproduced, rejectDefect } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import {
  useCurrentPolicy,
  useDefectDetail,
  useDefectReproductions,
  useDefectRootCause,
  useDefects,
} from "@/src/api/hooks/use-journey-queries";
import { useActorMe } from "@/src/api/hooks/use-olympus-queries";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const REJECT_STAGES = new Set([
  "TRIAGE",
  "REPRODUCTION",
  "EXPECTED_BEHAVIOR",
  "ROOT_CAUSE",
  "REGRESSION",
]);

function RejectDefectAction({
  defectId,
  projectId,
  cycleId,
}: {
  defectId: string;
  projectId: string;
  cycleId: string;
}) {
  const actor = useActorMe();
  const queryClient = useQueryClient();
  const canReject = (actor.data?.roles ?? []).includes("OPERATOR");
  const [reason, setReason] = useState("");
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idem, setIdem] = useState(() => newIdempotencyKey());

  const path = `/defects/${defectId}/reject`;
  const body = { reason: reason.trim() || null };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await rejectDefect(defectId, body.reason, idem);
      setReason("");
      setArmed(false);
      invalidateStudioCycle(queryClient, { projectId, cycleId });
    } catch (e) {
      setError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ol-ws-action">
      <p className="ol-label">Reject defect</p>
      {!canReject && (
        <p className="ol-body-sm ol-muted" role="status">
          You need the OPERATOR role to do this.
        </p>
      )}
      <label className="ol-field">
        <span className="ol-label">Reason (optional)</span>
        <textarea
          rows={2}
          value={reason}
          disabled={!canReject || busy}
          onChange={(ev) => setReason(ev.target.value)}
        />
      </label>
      {!armed ? (
        <Button
          variant="primary"
          disabled={!canReject || busy}
          onClick={() => {
            setIdem(newIdempotencyKey());
            setArmed(true);
          }}
        >
          Reject defect
        </Button>
      ) : (
        <>
          <p className="ol-body-sm ol-muted">Confirm rejection — this can cancel the delivery cycle.</p>
          <pre className="ol-cmd-api">{previewStudioPost(path, body, idem)}</pre>
          <div className="ol-ws-action-row">
            <Button disabled={busy} onClick={() => setArmed(false)}>
              Cancel
            </Button>
            <Button variant="primary" disabled={!canReject || busy} onClick={confirm}>
              Confirm reject
            </Button>
          </div>
        </>
      )}
      {error && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function ProceedUnreproducedAction({
  defectId,
  projectId,
  cycleId,
}: {
  defectId: string;
  projectId: string;
  cycleId: string;
}) {
  const actor = useActorMe();
  const policy = useCurrentPolicy();
  const queryClient = useQueryClient();
  const canProceed = (actor.data?.roles ?? []).includes("APPROVER");
  const policyOff = policy.data ? !policyAllowsUnreproduced(policy.data.content) : false;
  const enabled = canProceed && !policyOff && !policy.isLoading;
  const [reason, setReason] = useState("");
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [idem, setIdem] = useState(() => newIdempotencyKey());

  const path = `/defects/${defectId}/proceed-unreproduced`;
  const body = { reason: reason.trim() };
  const canSubmit = enabled && reason.trim().length > 0;

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await proceedUnreproduced(defectId, reason.trim(), idem);
      setReason("");
      setArmed(false);
      setDone(true);
      invalidateStudioCycle(queryClient, { projectId, cycleId });
    } catch (e) {
      setError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="ol-ws-action">
        <p className="ol-label">Proceed unreproduced</p>
        <p className="ol-body-sm ol-chat-ok" role="status">
          Proceeding without reproduction (approval recorded).
        </p>
      </div>
    );
  }

  return (
    <div className="ol-ws-action">
      <p className="ol-label">Proceed unreproduced</p>
      {!canProceed && (
        <p className="ol-body-sm ol-muted" role="status">
          You need the APPROVER role to do this.
        </p>
      )}
      {policyOff && (
        <p className="ol-body-sm ol-muted" role="status">
          Policy bugfix.allow_unreproduced is off, so this defect can&apos;t proceed without a
          reproduction.
        </p>
      )}
      <label className="ol-field">
        <span className="ol-label">Reason (required)</span>
        <textarea
          rows={3}
          value={reason}
          disabled={!enabled || busy}
          onChange={(ev) => setReason(ev.target.value)}
        />
      </label>
      {!armed ? (
        <Button
          variant="primary"
          disabled={!canSubmit || busy}
          onClick={() => {
            setIdem(newIdempotencyKey());
            setArmed(true);
          }}
        >
          Proceed unreproduced
        </Button>
      ) : (
        <>
          <pre className="ol-cmd-api">{previewStudioPost(path, body, idem)}</pre>
          <div className="ol-ws-action-row">
            <Button disabled={busy} onClick={() => setArmed(false)}>
              Cancel
            </Button>
            <Button variant="primary" disabled={!canSubmit || busy} onClick={confirm}>
              Confirm send
            </Button>
          </div>
        </>
      )}
      {error && (
        <p className="ol-body-sm ol-chat-err" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function BugFixStage({
  projectId,
  cycleId,
  stage,
}: {
  projectId: string;
  cycleId: string;
  stage: "TRIAGE" | "REPRODUCTION" | "EXPECTED_BEHAVIOR" | "ROOT_CAUSE" | "REGRESSION";
}) {
  const defects = useDefects(projectId);
  const forCycle = useMemo(
    () => (defects.data ?? []).filter((d) => d.delivery_cycle_id === cycleId),
    [defects.data, cycleId],
  );
  const [defectId, setDefectId] = useState<string | undefined>();
  const activeId = defectId ?? forCycle[0]?.id;
  const detail = useDefectDetail(activeId);
  const repros = useDefectReproductions(stage === "REPRODUCTION" ? activeId : undefined);
  const rca = useDefectRootCause(stage === "ROOT_CAUSE" ? activeId : undefined);

  const showProceed =
    stage === "REPRODUCTION" && detail.data && mayProceedUnreproduced(detail.data.status);

  const showReject =
    REJECT_STAGES.has(stage) &&
    detail.data &&
    mayRejectDefect(detail.data.status);

  const titles: Record<typeof stage, string> = {
    TRIAGE: "Triage",
    REPRODUCTION: "Reproduction",
    EXPECTED_BEHAVIOR: "Expected behavior",
    ROOT_CAUSE: "Root cause",
    REGRESSION: "Regression",
  };

  return (
    <StageWorkspaceFrame>
      <Panel title={titles[stage]} sub={`Defect records · ${stage}`}>
        {forCycle.length === 0 && !defects.isLoading && (
          <EmptyState title="No defect for cycle" description="Intake a defect for this bug-fix cycle." />
        )}
        <ul className="ol-ws-list">
          {forCycle.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                className={`ol-ws-list-btn ${activeId === d.id ? "is-on" : ""}`}
                onClick={() => setDefectId(d.id)}
              >
                {d.key} — {d.title} <StatusBadge status={d.status} />
              </button>
            </li>
          ))}
        </ul>
        {detail.data && (
          <div className="ol-ws-spec-read">
            <p>{detail.data.description}</p>
            {stage === "TRIAGE" && detail.data.triage != null && (
              <pre className="ol-ws-pre">{JSON.stringify(detail.data.triage, null, 2)}</pre>
            )}
            {stage === "EXPECTED_BEHAVIOR" && (
              <p className="ol-body-sm ol-muted">
                Linked AC ids: {detail.data.expected_ac_ids.join(", ") || "—"}
              </p>
            )}
          </div>
        )}
        {stage === "REPRODUCTION" && (
          <ul className="ol-ws-bullets">
            {(repros.data ?? []).map((r, i) => (
              <li key={i}>
                {String(r.phase ?? "—")} · {String(r.outcome ?? "—")} ·{" "}
                {String(r.commit_sha ?? "").slice(0, 8)}
              </li>
            ))}
          </ul>
        )}
        {showProceed && activeId && (
          <ProceedUnreproducedAction defectId={activeId} projectId={projectId} cycleId={cycleId} />
        )}
        {showReject && activeId && (
          <RejectDefectAction defectId={activeId} projectId={projectId} cycleId={cycleId} />
        )}
        {stage === "ROOT_CAUSE" && rca.data && (
          <pre className="ol-ws-pre">{JSON.stringify(rca.data, null, 2)}</pre>
        )}
        {stage === "REGRESSION" && (
          <p className="ol-body-sm ol-muted">
            Regression checks run in Integration / Assurance — use those stages for evidence.
          </p>
        )}
      </Panel>
    </StageWorkspaceFrame>
  );
}

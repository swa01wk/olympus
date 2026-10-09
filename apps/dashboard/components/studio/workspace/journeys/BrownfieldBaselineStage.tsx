"use client";

import { Button, EmptyState, Label, Panel, StatusBadge } from "@/components/primitives";
import { ProvisionalBaselinesPanel } from "@/components/studio/ProvisionalBaselinesPanel";
import { ProductSpecView } from "@/components/studio/ProductSpecView";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { previewStudioPost } from "@/lib/command-preview";
import {
  defaultPromotionDecision,
  promotionDecisionAllowed,
  promotionDecisionRequiresNote,
  promotionDecisionsForSubject,
} from "@/lib/promotion-decisions";
import { newIdempotencyKey } from "@/lib/utils";
import { recordPromotionDecision } from "@/src/api/commands";
import { isApiError } from "@/src/api/client";
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import { useReviewQueue } from "@/src/api/hooks/use-journey-queries";
import { useActorMe } from "@/src/api/hooks/use-olympus-queries";
import { queryKeys } from "@/src/api/query-keys";
import type { ReviewQueueItem } from "@/src/api/types/journey";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

type QueueFilter = "undecided" | "all";

/** Detail keys `BaselineService.review_queue` sends per subject_type. */
const REVIEW_QUEUE_DETAIL_FIELDS: Record<string, readonly { key: string; label: string }[]> = {
  FEATURE_SPEC: [
    { key: "lineage_key", label: "Lineage" },
    { key: "confidence", label: "Confidence" },
    { key: "claimed_confidence", label: "Claimed confidence" },
  ],
  BASELINE: [
    { key: "lineage_key", label: "Lineage" },
    { key: "check_ref", label: "Check" },
    { key: "source", label: "Source" },
  ],
  ARCHITECTURE: [{ key: "version", label: "Version" }],
  IMPLEMENTATION_SPEC: [{ key: "lineage_key", label: "Lineage" }],
  UNCERTAINTY: [{ key: "statement", label: "Statement" }],
};

function formatDetailValue(key: string, value: unknown): string {
  if (
    (key === "confidence" || key === "claimed_confidence") &&
    typeof value === "number" &&
    value >= 0 &&
    value <= 1
  ) {
    return `${Math.round(value * 100)}%`;
  }
  if (key === "version" && typeof value === "number") return `v${value}`;
  return String(value);
}

function ReviewQueueDetail({ item }: { item: ReviewQueueItem }) {
  const fields = (REVIEW_QUEUE_DETAIL_FIELDS[item.subject_type] ?? []).filter(
    ({ key }) => item.detail[key] != null && item.detail[key] !== "",
  );
  if (fields.length === 0) {
    return <p className="ol-body-sm ol-muted">No detail</p>;
  }
  return (
    <dl className="ol-appr-scope">
      {fields.map(({ key, label }) => (
        <div key={key}>
          <dt className="ol-label">{label}</dt>
          <dd className="ol-body-sm">{formatDetailValue(key, item.detail[key])}</dd>
        </div>
      ))}
    </dl>
  );
}

function ReviewQueueDecisionControls({
  cycleId,
  projectId,
  item,
  canApprove,
}: {
  cycleId: string;
  projectId: string;
  item: ReviewQueueItem;
  canApprove: boolean;
}) {
  const queryClient = useQueryClient();
  const options = promotionDecisionsForSubject(item.subject_type);
  const allowed = (decision: string) => promotionDecisionAllowed(decision, canApprove);
  const [selected, setSelected] = useState(() => defaultPromotionDecision(options, canApprove));
  const [note, setNote] = useState("");
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idem, setIdem] = useState(() => newIdempotencyKey());

  const readOnly = Boolean(selected) && !allowed(selected);
  const someDisabled = options.some((decision) => !allowed(decision));
  const noteRequired = promotionDecisionRequiresNote(selected);
  const body = {
    subject_type: item.subject_type,
    subject_id: item.subject_id,
    decision: selected,
    note: note.trim() || null,
  };
  const path = `/delivery-cycles/${cycleId}/promotion-decisions`;
  const canSubmit =
    Boolean(selected) &&
    !readOnly &&
    (!noteRequired || note.trim().length > 0);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await recordPromotionDecision(cycleId, body, idem);
      setNote("");
      setArmed(false);
      invalidateStudioCycle(queryClient, { projectId, cycleId });
    } catch (e) {
      setError(isApiError(e) ? e.message : e instanceof Error ? e.message : "Decision failed");
      void queryClient.invalidateQueries({ queryKey: queryKeys.journey.reviewQueue(cycleId) });
    } finally {
      setBusy(false);
    }
  };

  if (item.decided) {
    return (
      <p className="ol-body-sm">
        Decision: <StatusBadge status={item.decision ?? "DECIDED"} />
      </p>
    );
  }

  return (
    <div className="ol-ws-action">
      <Label>Promotion decision</Label>
      <div className="ol-ws-action-row" role="radiogroup" aria-label="Decision">
        {options.map((decision) => {
          const disabled = !allowed(decision);
          return (
            <label key={decision} className="ol-body-sm">
              <input
                type="radio"
                name={`decision-${item.subject_id}`}
                value={decision}
                checked={selected === decision}
                disabled={disabled}
                onChange={() => {
                  setSelected(decision);
                  setArmed(false);
                  setIdem(newIdempotencyKey());
                }}
              />{" "}
              {decision.replace(/_/g, " ")}
            </label>
          );
        })}
      </div>
      {someDisabled && (
        <p className="ol-body-sm ol-muted" role="status">
          You need the APPROVER role to do this.
        </p>
      )}
      {item.subject_type === "BASELINE" && selected === "ACTIVATE" && (
        <p className="ol-body-sm ol-muted">Activation needs passing evidence for this check.</p>
      )}
      <label className="ol-field">
        <span className="ol-label">
          Note{noteRequired ? " (required)" : " (optional)"}
        </span>
        <textarea
          rows={2}
          value={note}
          disabled={readOnly || busy}
          onChange={(ev) => setNote(ev.target.value)}
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
          Preview decision
        </Button>
      ) : (
        <>
          <pre className="ol-cmd-api">{previewStudioPost(path, body, idem)}</pre>
          <div className="ol-ws-action-row">
            <Button disabled={busy} onClick={() => setArmed(false)}>
              Cancel
            </Button>
            <Button variant="primary" disabled={!canSubmit || busy} onClick={submit}>
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

export function BrownfieldBaselineStage({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  const queue = useReviewQueue(cycleId);
  const actor = useActorMe();
  const canApprove = (actor.data?.roles ?? []).includes("APPROVER");
  const [filter, setFilter] = useState<QueueFilter>("undecided");

  const items = useMemo(() => {
    const all = queue.data ?? [];
    if (filter === "all") return all;
    return all.filter((item) => !item.decided);
  }, [queue.data, filter]);

  return (
    <StageWorkspaceFrame>
      <ProductSpecView projectId={projectId} />
      <ProvisionalBaselinesPanel projectId={projectId} />
      <Panel title="Review queue" sub={`GET /delivery-cycles/${cycleId}/review-queue`}>
        <div className="ol-seg" role="radiogroup" aria-label="Queue filter">
          <button
            type="button"
            role="radio"
            aria-checked={filter === "undecided"}
            className={`ol-seg-i${filter === "undecided" ? " is-on" : ""}`}
            onClick={() => setFilter("undecided")}
          >
            Undecided
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={filter === "all"}
            className={`ol-seg-i${filter === "all" ? " is-on" : ""}`}
            onClick={() => setFilter("all")}
          >
            All
          </button>
        </div>
        <p className="ol-body-sm ol-muted">
          Promoted, confirmed, rejected and activated items leave the queue.
        </p>
        {queue.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {items.length === 0 && !queue.isLoading && (
          <EmptyState
            title={filter === "undecided" ? "Nothing pending" : "Queue empty"}
            description="Promotion decisions appear when recovered artifacts need review."
          />
        )}
        <ul className="ol-ws-list">
          {items.map((item) => (
            <li key={`${item.subject_type}-${item.subject_id}`} className="ol-ws-row ol-appr">
              <div>
                <span className="ol-id">{item.subject_type}</span>{" "}
                <span className="ol-id">{item.subject_id}</span>
              </div>
              <ReviewQueueDetail item={item} />
              {!actor.isPending && (
                <ReviewQueueDecisionControls
                  cycleId={cycleId}
                  projectId={projectId}
                  item={item}
                  canApprove={canApprove}
                />
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </StageWorkspaceFrame>
  );
}

"use client";

import { Button, EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { ExceptionState } from "@/components/truth/ExceptionState";
import { previewClarificationAnswer } from "@/lib/command-preview";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import type { InboxItem } from "@/src/api/types/core";
import type { FeatureSpecBody } from "@/src/api/types/product-model";
import {
  useAnswerClarification,
  useCreateFeatureSpecVersion,
} from "@/src/api/hooks/use-studio-mutations";
import {
  useCapabilities,
  useClarifications,
  useFeatureSpecDetail,
  useFeatureSpecs,
  useAllFeatureSpecSummaries,
  useFeatures,
} from "@/src/api/hooks/use-studio-queries";
import { requestScopeApproval } from "@/src/api/commands";
import { useMemo, useState } from "react";

const SCOPE_SPEC_STATUSES = new Set(["PROPOSED", "DRAFT"]);

function SpecEditor({
  initial,
  onSave,
  busy,
}: {
  initial: FeatureSpecBody;
  onSave: (body: FeatureSpecBody) => void;
  busy: boolean;
}) {
  const [body, setBody] = useState(initial);
  return (
    <form
      className="ol-ws-spec-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(body);
      }}
    >
      {(
        [
          ["summary", "Summary"],
          ["behavior", "Behavior"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="ol-ws-field">
          <span className="ol-label">{label}</span>
          <textarea
            value={body[key]}
            rows={key === "behavior" ? 6 : 3}
            onChange={(e) => setBody((b) => ({ ...b, [key]: e.target.value }))}
          />
        </label>
      ))}
      {(["inputs", "outputs", "rules"] as const).map((key) => (
        <label key={key} className="ol-ws-field">
          <span className="ol-label">{key}</span>
          <textarea
            value={body[key].join("\n")}
            rows={3}
            onChange={(e) =>
              setBody((b) => ({
                ...b,
                [key]: e.target.value.split("\n").filter(Boolean),
              }))
            }
          />
        </label>
      ))}
      <Button type="submit" variant="primary" disabled={busy}>
        Save new version
      </Button>
    </form>
  );
}

export function ProductModelStage({
  projectId,
  cycleId,
  inbox,
}: {
  projectId: string;
  cycleId: string;
  inbox: InboxItem[];
}) {
  const scope = { projectId, cycleId };
  const capabilities = useCapabilities(projectId);
  const features = useFeatures(projectId);
  const clarifications = useClarifications("OPEN");
  const scopePending = inbox.some(
    (i) => i.approval?.approval_type === "SCOPE" && i.approval.status === "PENDING",
  );

  const [featureId, setFeatureId] = useState<string | undefined>();
  const [specId, setSpecId] = useState<string | undefined>();
  const [editing, setEditing] = useState(false);
  const [clarAnswer, setClarAnswer] = useState<Record<string, string>>({});

  const specs = useFeatureSpecs(featureId);
  const specDetail = useFeatureSpecDetail(specId);
  const saveSpec = useCreateFeatureSpecVersion(scope, featureId ?? "");
  const answerClar = useAnswerClarification(scope);
  const featureIds = useMemo(
    () => (features.data ?? []).map((f) => f.id),
    [features.data],
  );
  const allSpecQueries = useAllFeatureSpecSummaries(featureIds);

  const featuresByCap = useMemo(() => {
    const map = new Map<string | null, typeof features.data>();
    for (const f of features.data ?? []) {
      const k = f.capability_id;
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(f);
    }
    return map;
  }, [features]);

  const scopeSpecIds = useMemo(() => {
    const ids: string[] = [];
    for (const q of allSpecQueries) {
      for (const s of q.data ?? []) {
        if (SCOPE_SPEC_STATUSES.has(s.status)) ids.push(s.id);
      }
    }
    return ids;
  }, [allSpecQueries]);

  const selectedSpecs = specs.data ?? [];
  const latestSpec = selectedSpecs[selectedSpecs.length - 1];
  const activeSpecId = specId ?? latestSpec?.id;

  return (
    <StageWorkspaceFrame>
      <div className="ol-ws-split">
        <Panel title="Capabilities & features" sub="Product model tree">
          {features.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
          {features.isError && (
            <ExceptionState status="ERROR" reason="Could not load features." />
          )}
          {(capabilities.data ?? []).map((cap) => (
            <div key={cap.id} className="ol-ws-tree-group">
              <p className="ol-label">
                {cap.key} · {cap.name}
              </p>
              <ul className="ol-ws-list">
                {(featuresByCap.get(cap.id) ?? []).map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      className={`ol-ws-list-btn ${featureId === f.id ? "is-on" : ""}`}
                      onClick={() => {
                        setFeatureId(f.id);
                        setSpecId(undefined);
                        setEditing(false);
                      }}
                    >
                      {f.key} — {f.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {(featuresByCap.get(null) ?? []).length > 0 && (
            <div className="ol-ws-tree-group">
              <p className="ol-label">Unscoped</p>
              <ul className="ol-ws-list">
                {(featuresByCap.get(null) ?? []).map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      className={`ol-ws-list-btn ${featureId === f.id ? "is-on" : ""}`}
                      onClick={() => {
                        setFeatureId(f.id);
                        setSpecId(undefined);
                        setEditing(false);
                      }}
                    >
                      {f.key}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!features.isLoading && (features.data ?? []).length === 0 && (
            <EmptyState title="No features" description="Decompose a PRD in Discovery first." />
          )}
        </Panel>
        <Panel
          title="Feature spec"
          sub={featureId ? `Feature ${featureId.slice(0, 8)}…` : "Select a feature"}
        >
          {!featureId && <p className="ol-body-sm ol-muted">Select a feature on the left.</p>}
          {featureId && (
            <>
              <ul className="ol-ws-chips">
                {selectedSpecs.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      className={`ol-ws-chip ${activeSpecId === s.id ? "is-on" : ""}`}
                      onClick={() => {
                        setSpecId(s.id);
                        setEditing(false);
                      }}
                    >
                      v{s.version} <StatusBadge status={s.status} />
                    </button>
                  </li>
                ))}
              </ul>
              {specDetail.isLoading && activeSpecId && (
                <p className="ol-body-sm ol-muted">Loading spec…</p>
              )}
              {specDetail.data && !editing && (
                <div className="ol-ws-spec-read">
                  <p className="ol-body-sm">
                    <StatusBadge status={specDetail.data.status} /> v{specDetail.data.version}
                  </p>
                  <h4 className="ol-label">Summary</h4>
                  <p>{specDetail.data.body.summary}</p>
                  <h4 className="ol-label">Behavior</h4>
                  <p>{specDetail.data.body.behavior}</p>
                  <SpecList label="Inputs" items={specDetail.data.body.inputs} />
                  <SpecList label="Outputs" items={specDetail.data.body.outputs} />
                  <SpecList label="Rules" items={specDetail.data.body.rules} />
                  {specDetail.data.body.constraints?.length ? (
                    <SpecList label="Constraints" items={specDetail.data.body.constraints} />
                  ) : null}
                  {specDetail.data.body.out_of_scope?.length ? (
                    <SpecList label="Out of scope" items={specDetail.data.body.out_of_scope} />
                  ) : null}
                  <Button variant="quiet" onClick={() => setEditing(true)}>
                    Edit spec
                  </Button>
                </div>
              )}
              {specDetail.data && editing && (
                <SpecEditor
                  initial={specDetail.data.body}
                  busy={saveSpec.isPending}
                  onSave={async (body) => {
                    await saveSpec.mutateAsync(body);
                    setEditing(false);
                  }}
                />
              )}
            </>
          )}
        </Panel>
      </div>
      <Panel title="Scope sign-off" sub="Request approval for all PROPOSED/DRAFT specs">
        <StudioMutationAction
          label="Request scope approval"
          path={`/delivery-cycles/${cycleId}/scope/approval-request`}
          body={{ feature_spec_ids: scopeSpecIds }}
          disabled={scopePending || scopeSpecIds.length === 0}
          onRun={(idem) => requestScopeApproval(cycleId, scopeSpecIds, idem)}
        />
        {scopePending && (
          <p className="ol-body-sm ol-muted">SCOPE approval pending — decide in workspace (C5).</p>
        )}
      </Panel>
      <Panel title="Open clarifications" sub="Answer to unblock downstream work">
        {(clarifications.data ?? []).length === 0 && (
          <p className="ol-body-sm ol-muted">No open clarifications.</p>
        )}
        <ul className="ol-ws-clar-list">
          {(clarifications.data ?? []).map((c) => (
            <li key={c.id} className="ol-ws-clar">
              <p className="ol-id">{c.key}</p>
              <p>{c.question}</p>
              <textarea
                rows={2}
                value={clarAnswer[c.id] ?? ""}
                onChange={(e) => setClarAnswer((m) => ({ ...m, [c.id]: e.target.value }))}
              />
              <pre className="ol-cmd-api">{previewClarificationAnswer(c.id, clarAnswer[c.id] ?? "")}</pre>
              <Button
                variant="primary"
                disabled={!clarAnswer[c.id]?.trim() || answerClar.isPending}
                onClick={() =>
                  answerClar.mutate({ clarificationId: c.id, answer: clarAnswer[c.id]!.trim() })
                }
              >
                Send answer
              </Button>
            </li>
          ))}
        </ul>
      </Panel>
    </StageWorkspaceFrame>
  );
}

function SpecList({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <>
      <h4 className="ol-label">{label}</h4>
      <ul className="ol-ws-bullets">
        {items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </>
  );
}

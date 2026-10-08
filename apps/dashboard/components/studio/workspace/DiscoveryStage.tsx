"use client";

import { Button, EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { previewStudioPost } from "@/lib/command-preview";
import { newIdempotencyKey } from "@/lib/utils";
import { ExceptionState } from "@/components/truth/ExceptionState";
import { RunningNotice } from "@/components/studio/workspace/RunningNotice";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import {
  useDecomposeSource,
  useUploadProductSource,
} from "@/src/api/hooks/use-studio-mutations";
import {
  useDecompositions,
  useSourceContent,
  useSources,
} from "@/src/api/hooks/use-studio-queries";
import { useRegisterStudioFocus } from "@/lib/studio-focus";
import { decomposeSource } from "@/src/api/commands";
import { useRef, useState } from "react";

const PRD_ACCEPT = ".md,.txt,.pdf";

export function DiscoveryStage({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  const scope = { projectId, cycleId };
  const sources = useSources(projectId);
  const decompositions = useDecompositions(cycleId);
  const upload = useUploadProductSource(scope);
  const decompose = useDecomposeSource(scope);
  const [selectedSourceId, setSelectedSourceId] = useState<string | undefined>();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploadPreviewKey, setUploadPreviewKey] = useState(() => newIdempotencyKey());

  const sortedSources = [...(sources.data ?? [])].sort((a, b) => b.version - a.version);
  const activeSourceId = selectedSourceId ?? sortedSources[0]?.id;
  const content = useSourceContent(projectId, activeSourceId);

  const activeDecomp = (decompositions.data ?? []).find(
    (d) => d.status === "PROPOSED" && d.execution_id,
  );
  const decomposeBusy = Boolean(activeDecomp);

  useRegisterStudioFocus(
    activeSourceId ? { subject_type: "product_source", subject_id: activeSourceId } : null,
  );

  const confirmUpload = async () => {
    if (!pendingFile) return;
    await upload.mutateAsync({ file: pendingFile });
    setPendingFile(null);
    setUploadPreviewKey(newIdempotencyKey());
  };

  return (
    <StageWorkspaceFrame>
      {sources.isError && (
        <ExceptionState
          status="ERROR"
          reason="Could not load product sources."
          consequence="Check API connectivity and permissions."
        />
      )}
      <div className="ol-ws-split">
        <Panel title="Sources" sub="PRD versions ingested for this project">
          {sources.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
          {!sources.isLoading && sortedSources.length === 0 && (
            <EmptyState
              title="No PRD yet"
              description="Upload a PRD from here or attach one in chat."
              action={{
                label: "Upload PRD",
                onClick: () => fileRef.current?.click(),
              }}
            />
          )}
          <ul className="ol-ws-list">
            {sortedSources.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`ol-ws-list-btn ${activeSourceId === s.id ? "is-on" : ""}`}
                  onClick={() => setSelectedSourceId(s.id)}
                >
                  <span className="ol-id">v{s.version}</span> {s.title}
                </button>
              </li>
            ))}
          </ul>
          <Button variant="primary" disabled={upload.isPending} onClick={() => fileRef.current?.click()}>
            Upload PRD
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept={PRD_ACCEPT}
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setPendingFile(f);
                setUploadPreviewKey(newIdempotencyKey());
              }
              e.target.value = "";
            }}
          />
          {pendingFile && (
            <div className="ol-ws-action">
              <pre className="ol-cmd-api">
                {previewStudioPost(
                  `/projects/${projectId}/sources?delivery_cycle_id=${cycleId}`,
                  { file: pendingFile.name, multipart: true },
                  uploadPreviewKey,
                )}
              </pre>
              <div className="ol-ws-action-row">
                <Button variant="primary" disabled={upload.isPending} onClick={confirmUpload}>
                  Confirm send
                </Button>
                <Button variant="quiet" onClick={() => setPendingFile(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
          {activeSourceId && (
            <StudioMutationAction
              label="Decompose source"
              path={`/sources/${activeSourceId}/decompose`}
              body={{ delivery_cycle_id: cycleId }}
              disabled={decomposeBusy || decompose.isPending}
              onRun={(idem) => decomposeSource(activeSourceId, cycleId, idem)}
            />
          )}
          {activeDecomp?.execution_id && (
            <RunningNotice executionId={activeDecomp.execution_id} label="decomposition" />
          )}
        </Panel>
        <Panel title="Source content" sub="Markdown / plain text from the backend">
          {!activeSourceId && <p className="ol-body-sm ol-muted">Select a source.</p>}
          {content.isLoading && activeSourceId && <p className="ol-body-sm ol-muted">Loading…</p>}
          {content.isError && (
            <ExceptionState status="ERROR" reason="Could not load source content." />
          )}
          {content.data && (
            <article className="ol-ws-markdown">
              <h3 className="ol-section">{content.data.title}</h3>
              <pre className="ol-ws-pre">{content.data.text}</pre>
            </article>
          )}
        </Panel>
      </div>
      <Panel title="Decomposition" sub={`GET /delivery-cycles/${cycleId}/decompositions`}>
        {(decompositions.data ?? []).length === 0 && (
          <p className="ol-body-sm ol-muted">No decomposition runs for this cycle yet.</p>
        )}
        <ul className="ol-ws-list">
          {(decompositions.data ?? []).map((d) => (
            <li key={d.id} className="ol-ws-row">
              <span className="ol-id">{d.id.slice(0, 8)}</span>
              <StatusBadge status={d.status} />
              {d.execution_id && (
                <RunningNotice executionId={d.execution_id} label="agent run" />
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </StageWorkspaceFrame>
  );
}

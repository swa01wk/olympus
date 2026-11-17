"use client";

import { useArchitectureDetail, useFeatures } from "@/src/api/hooks/use-studio-queries";
import { queryKeys } from "@/src/api/query-keys";
import { fetchImplementationSpec, fetchTaskPlan } from "@/src/api/resources";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

type Props = { approvalType: string; subjectId: string; projectId: string };

/** What the person is approving, in plain terms; raw details stay in Inspect. */
export function ApprovalSubject({ approvalType, subjectId, projectId }: Props) {
  switch (approvalType) {
    case "SCOPE":
      return <FeatureList projectId={projectId} />;
    case "ARCHITECTURE":
    case "ARCHITECTURE_DELTA":
      return <Design architectureId={subjectId} />;
    case "IMPLEMENTATION_SPEC":
      return <FeaturePlan specId={subjectId} />;
    case "TASK_PLAN":
      return <TaskList planId={subjectId} />;
    case "RELEASE":
      return (
        <Box>
          <p style={{ margin: 0 }}>
            The code is merged, the tests pass and the review is done. Approving tags this version
            as a release.
          </p>
        </Box>
      );
    default:
      return null;
  }
}

function Box({ children }: { children: ReactNode }) {
  return <div className="sp-subject">{children}</div>;
}

function Loading({ what }: { what: string }) {
  return <Box>Loading {what}…</Box>;
}

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter((v): v is Record<string, unknown> => typeof v === "object" && v !== null)
    : [];
}

function FeatureList({ projectId }: { projectId: string }) {
  const features = useFeatures(projectId);
  if (features.isLoading) return <Loading what="features" />;
  const rows = features.data ?? [];
  if (rows.length === 0) return <Box>No features found.</Box>;
  return (
    <Box>
      <h4>{rows.length} features</h4>
      <ul>
        {rows.map((f) => (
          <li key={f.id}>
            <strong>{f.name}</strong>
            {f.description && <span className="sp-muted"> — {f.description}</span>}
          </li>
        ))}
      </ul>
    </Box>
  );
}

function Design({ architectureId }: { architectureId: string }) {
  const arch = useArchitectureDetail(architectureId);
  if (arch.isLoading) return <Loading what="the design" />;
  const body = (arch.data?.body ?? {}) as Record<string, unknown>;
  const stack = (body.technology_stack ?? {}) as Record<string, unknown>;
  const stackLine = ["language", "web", "orm", "tests"]
    .map((k) => stack[k])
    .filter((v): v is string => typeof v === "string" && v.length > 0)
    .join(" · ");
  const components = asRecords(body.components);
  const decisions = asRecords(body.decisions);
  const risks = asStrings(body.risks);
  return (
    <Box>
      {typeof body.summary === "string" && <p style={{ marginTop: 0 }}>{body.summary}</p>}
      {stackLine && (
        <>
          <h4>Stack</h4>
          <p style={{ margin: 0 }}>{stackLine}</p>
        </>
      )}
      {components.length > 0 && (
        <>
          <h4>Parts</h4>
          <ul>
            {components.map((c, i) => (
              <li key={String(c.name ?? i)}>
                <strong>{String(c.name ?? "Part")}</strong>
                {typeof c.responsibility === "string" && (
                  <span className="sp-muted"> — {c.responsibility}</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {decisions.length > 0 && (
        <>
          <h4>Key decisions</h4>
          <ul>
            {decisions.map((d, i) => (
              <li key={String(d.id ?? i)}>
                {String(d.title ?? d.decision ?? "")}
                {typeof d.rationale === "string" && (
                  <span className="sp-muted"> — {d.rationale}</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {risks.length > 0 && (
        <>
          <h4>Risks</h4>
          <ul>
            {risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}
    </Box>
  );
}

function FeaturePlan({ specId }: { specId: string }) {
  const spec = useQuery({
    queryKey: ["implementation-spec", specId],
    queryFn: () => fetchImplementationSpec(specId),
  });
  if (spec.isLoading) return <Loading what="the plan" />;
  const body = (spec.data?.body ?? {}) as Record<string, unknown>;
  const files = asStrings(body.file_scope);
  const tests = asRecords(body.required_tests);
  const apis = asRecords(body.apis);
  return (
    <Box>
      {typeof body.summary === "string" && <p style={{ marginTop: 0 }}>{body.summary}</p>}
      {apis.length > 0 && (
        <>
          <h4>Endpoints</h4>
          <ul>
            {apis.map((a, i) => (
              <li key={i}>
                <code className="sp-code">
                  {String(a.method ?? "")} {String(a.path ?? a.name ?? "")}
                </code>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="sp-small sp-muted" style={{ marginBottom: 0 }}>
        Touches {files.length} {files.length === 1 ? "file" : "files"} · {tests.length} required{" "}
        {tests.length === 1 ? "test" : "tests"}
      </p>
    </Box>
  );
}

function TaskList({ planId }: { planId: string }) {
  const plan = useQuery({
    queryKey: queryKeys.taskPlans.detail(planId),
    queryFn: () => fetchTaskPlan(planId),
  });
  if (plan.isLoading) return <Loading what="the task list" />;
  const tasks = asRecords((plan.data?.body ?? {}).tasks);
  return (
    <Box>
      <h4>{tasks.length} tasks, in order</h4>
      <ol style={{ margin: 0, paddingLeft: 18 }}>
        {tasks.map((t, i) => (
          <li key={String(t.ref ?? i)}>{String(t.title ?? t.ref ?? "Task")}</li>
        ))}
      </ol>
    </Box>
  );
}

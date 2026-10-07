"use client";

import { AppShell } from "@/components/shell/AppShell";
import { KV, Panel } from "@/components/primitives";
import { useAuditTarget, useAuditVerify } from "@/src/api/hooks/use-drill-queries";
import { useDeliveryCycles, useProject } from "@/src/api/hooks/use-olympus-queries";
import { useSearchParams } from "next/navigation";

export function AuditScreen() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project") ?? "";
  const project = useProject(projectId || undefined);
  const cycles = useDeliveryCycles(projectId || undefined);
  const verify = useAuditVerify(projectId || undefined);
  const audit = useAuditTarget("project", projectId || undefined);

  return (
    <AppShell
      project={project.data}
      cycles={cycles.data ?? []}
      cycleId={cycles.data?.[0]?.id ?? ""}
      onCycleChange={() => {}}
      stream={{ state: "disconnected", lastEventAt: null, lastRefreshAt: null }}
    >
      <div className="ol-screen">
        <h1 className="ol-title">Audit history</h1>
        {!projectId && (
          <p className="text-sm ol-muted">Open with ?project=&lt;uuid&gt; for project-scoped chain verify.</p>
        )}
        {projectId && verify.data && (
          <Panel title="Chain verification" sub="Tamper-evident audit log">
            <KV
              rows={[
                ["Valid", verify.data.valid ? "yes" : "no"],
                ["Rows checked", String(verify.data.rows_checked)],
                ["Message", verify.data.message],
              ]}
            />
          </Panel>
        )}
        {projectId && (
          <Panel title="Project audit events" sub="target_type=project">
            <ul className="text-sm flex flex-col gap-2 max-h-96 overflow-auto">
              {(audit.data ?? []).map((row) => (
                <li key={row.id} className="border border-[var(--border)] p-2 rounded">
                  <strong>{row.action}</strong>
                  <span className="ol-muted text-xs ml-2">{row.occurred_at}</span>
                </li>
              ))}
              {!audit.data?.length && !audit.isLoading && (
                <p className="ol-muted">No audit rows for this target.</p>
              )}
            </ul>
          </Panel>
        )}
      </div>
    </AppShell>
  );
}

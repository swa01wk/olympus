"use client";

import { StatusBadge } from "@/components/primitives";

type Row = {
  obligation_id?: string;
  subject_key?: string;
  evidence_key?: string;
  commit_sha?: string;
  result?: string;
  satisfied?: boolean;
  target_sha?: string;
};

export function EvidenceMatrix({
  obligations,
  evidence,
  coverage,
  targetSha,
}: {
  obligations: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  coverage: Record<string, unknown>[];
  targetSha?: string | null;
}) {
  const rows: Row[] = coverage.length
    ? coverage.map((c) => {
        const ob = obligations.find((o) => o.id === c.obligation_id);
        const ev = evidence.find((e) => e.id === c.evidence_id);
        const sha = (ev?.commit_sha as string | undefined) ?? null;
        return {
          obligation_id: c.obligation_id as string,
          subject_key: ob?.subject_key as string | undefined,
          evidence_key: ev?.key as string | undefined,
          commit_sha: sha ?? undefined,
          result: ev?.result as string | undefined,
          satisfied: Boolean(c.satisfied),
          target_sha: targetSha ?? undefined,
        };
      })
    : obligations.map((o) => ({
        subject_key: o.subject_key as string,
        result: o.status as string,
        satisfied: o.status === "SATISFIED",
      }));

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left ol-muted">
            <th className="p-2 border-b border-[var(--border)]">Obligation</th>
            <th className="p-2 border-b border-[var(--border)]">Evidence</th>
            <th className="p-2 border-b border-[var(--border)]">Target SHA</th>
            <th className="p-2 border-b border-[var(--border)]">Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const stale =
              r.target_sha && r.commit_sha && r.commit_sha !== r.target_sha;
            return (
              <tr key={i} className="border-b border-[var(--border)]">
                <td className="p-2">{r.subject_key ?? r.obligation_id ?? "—"}</td>
                <td className="p-2">{r.evidence_key ?? "—"}</td>
                <td className="p-2 font-mono text-xs">
                  {r.commit_sha?.slice(0, 10) ?? "—"}
                  {stale && (
                    <span className="block text-[var(--warning)] text-xs">Not current target</span>
                  )}
                </td>
                <td className="p-2">
                  {r.result ? <StatusBadge status={r.result} /> : r.satisfied ? "Satisfied" : "Open"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rows.length && <p className="text-sm ol-muted p-2">No obligations loaded for this candidate.</p>}
    </div>
  );
}

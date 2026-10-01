import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { ActionRequest } from "@/lib/contracts/entity-types";

export function ActionTimeline({ actions }: { actions: ActionRequest[] }) {
  const sorted = [...actions].sort((a, b) =>
    (b.requested_at ?? "").localeCompare(a.requested_at ?? ""),
  );

  return (
    <Panel title="Action timeline" stateRail="running" actions={<FixtureBadge />}>
      <table className="w-full text-left text-xs">
        <thead className="text-[var(--muted)]">
          <tr>
            <th className="p-1">time</th>
            <th className="p-1">tool</th>
            <th className="p-1">target</th>
            <th className="p-1">status</th>
            <th className="p-1">policy</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((a) => (
            <tr key={a.id} className="border-t border-[var(--border)]">
              <td className="p-1 font-mono text-[10px]">{a.requested_at?.slice(11, 19) ?? "—"}</td>
              <td className="p-1 font-mono">{a.tool}</td>
              <td className="p-1">
                {a.resource}.{a.action}
              </td>
              <td className="p-1">
                <StatusBadge value={a.status} />
              </td>
              <td className="p-1 font-mono text-[10px]">
                {a.policy_decision?.decision}
                {a.policy_decision?.rule_ids?.length ? ` (${a.policy_decision.rule_ids.join(",")})` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

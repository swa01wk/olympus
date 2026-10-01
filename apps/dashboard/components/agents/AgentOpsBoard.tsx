"use client";

import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { ActionRequest, Execution } from "@/lib/contracts/entity-types";
import { isExecutionActive } from "@/lib/utils/execution-active";

const CAPABILITIES = [
  "kira",
  "atlas",
  "forge",
  "warden",
  "sentinel",
  "scout",
  "impact",
  "stratos",
  "olympus_deterministic",
] as const;

function laneForProfile(profile: string | null | undefined): string {
  if (!profile) return "olympus_deterministic";
  if (profile.includes("warden")) return "warden";
  if (profile.includes("sentinel")) return "sentinel";
  if (profile.includes("forge") || profile.includes("implementation")) return "forge";
  if (profile.includes("kira")) return "kira";
  if (profile.includes("atlas")) return "atlas";
  if (profile.includes("scout")) return "scout";
  if (profile.includes("impact")) return "impact";
  if (profile.includes("stratos")) return "stratos";
  return "olympus_deterministic";
}

export function AgentOpsBoard({
  executions,
  actions,
}: {
  executions: Execution[];
  actions: ActionRequest[];
}) {
  const lanes = new Map<string, { execs: Execution[]; actions: ActionRequest[] }>();
  CAPABILITIES.forEach((c) => lanes.set(c, { execs: [], actions: [] }));

  executions.forEach((e) => {
    const lane = laneForProfile(e.agent_profile);
    const key = CAPABILITIES.includes(lane as (typeof CAPABILITIES)[number]) ? lane : "olympus_deterministic";
    lanes.get(key)!.execs.push(e);
  });
  actions.forEach((a) => {
    const lane = laneForProfile(a.tool.includes("olympus") ? "olympus_deterministic" : a.tool);
    lanes.get(lane)?.actions.push(a);
  });

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {CAPABILITIES.map((cap) => {
        const data = lanes.get(cap)!;
        const active = data.execs.filter((e) => isExecutionActive(e.status)).length;
        return (
          <Panel
            key={cap}
            title={cap.replace("_", " ")}
            stateRail={active ? "running" : "neutral"}
            actions={<FixtureBadge />}
          >
            <p className="mb-2 text-[10px] text-[var(--muted)]">
              {data.execs.length} executions · {active} active
            </p>
            <ul className="space-y-1 text-xs">
              {data.execs.slice(0, 4).map((e) => (
                <li key={e.id}>
                  <Link href={`/executions/${e.id}`} className="font-mono text-sky-300 hover:underline">
                    {e.key}
                  </Link>{" "}
                  <StatusBadge value={e.status} kind="execution" />
                </li>
              ))}
            </ul>
            {data.actions.length > 0 && (
              <p className="mt-2 text-[10px] text-violet-300">{data.actions.length} recent actions</p>
            )}
          </Panel>
        );
      })}
    </div>
  );
}

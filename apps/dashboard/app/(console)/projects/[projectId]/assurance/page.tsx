"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { RecommendationVsGate } from "@/components/assurance/RecommendationVsGate";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";
import { qk } from "@/lib/query/keys";

export default function AssurancePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const tab = search.get("tab") ?? "control-room";
  const cycleId = useActiveCycleId(projectId);

  const icsQ = useQuery({
    queryKey: qk.ics(cycleId ?? ""),
    queryFn: async () => (await getServices()).integration.listByCycle(cycleId!),
    enabled: !!cycleId,
  });

  const icFromUrl = search.get("ic");
  const icId =
    icFromUrl ?? icsQ.data?.find((ic) => ic.status !== "SUPERSEDED")?.id ?? null;

  const gatesQ = useQuery({
    queryKey: qk.gates(icId ?? ""),
    queryFn: async () => (await getServices()).assurance.gatesForIc(icId!),
    enabled: !!icId,
  });

  const findingsQ = useQuery({
    queryKey: qk.findings(cycleId ?? ""),
    queryFn: async () => (await getServices()).assurance.findings(cycleId!),
    enabled: !!cycleId,
  });

  const warden = gatesQ.data?.find((g) => g.gate_type === "WARDEN");
  const sentinel = gatesQ.data?.find((g) => g.gate_type === "SENTINEL");

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Assurance</h1>
      <nav className="flex flex-wrap gap-2 text-xs">
        {(["control-room", "evidence", "findings", "gates"] as const).map((t) => (
          <a
            key={t}
            href={`/projects/${projectId}/assurance?tab=${t}${cycleId ? `&cycle=${cycleId}` : ""}${icId ? `&ic=${icId}` : ""}`}
            className={`rounded border px-2 py-1 ${tab === t ? "border-amber-500" : "border-[var(--border)]"}`}
          >
            {t}
          </a>
        ))}
      </nav>

      {tab === "control-room" && (
        <>
          <p className="text-xs text-[var(--muted)]">Project {projectId} — IC {icId?.slice(0, 8) ?? "—"}</p>
          {warden && (
            <section>
              <h2 className="mb-2 text-sm font-semibold uppercase">Warden</h2>
              <RecommendationVsGate gate={warden} />
            </section>
          )}
          {sentinel && (
            <section>
              <h2 className="mb-2 text-sm font-semibold uppercase">Sentinel</h2>
              <RecommendationVsGate gate={sentinel} />
            </section>
          )}
          <Panel title="Olympus gates" stateRail="neutral" actions={<FixtureBadge />}>
            <ul className="text-xs">
              {gatesQ.data?.map((g) => (
                <li key={g.id}>
                  {g.gate_type}: {g.status}
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}

      {tab === "findings" && (
        <Panel title="Findings" stateRail="blocked" actions={<FixtureBadge />}>
          <ul className="text-sm">
            {findingsQ.data?.map((f) => (
              <li key={f.id} className={f.blocking ? "text-rose-300" : ""}>
                {f.key}: {f.title}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {tab === "gates" && gatesQ.data && (
        <div className="space-y-4">
          {gatesQ.data.map((g) => (
            <RecommendationVsGate key={g.id} gate={g} />
          ))}
        </div>
      )}

      {tab === "evidence" && (
        <Panel title="Evidence registry" stateRail="neutral" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">
            Evidence items linked from fixture assurance module — open Integration IC for SHA context.
          </p>
        </Panel>
      )}
    </div>
  );
}

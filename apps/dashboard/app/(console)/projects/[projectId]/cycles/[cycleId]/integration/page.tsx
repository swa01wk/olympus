"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { IcForge } from "@/components/integration/IcForge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export default function CycleIntegrationPage() {
  const { projectId, cycleId } = useParams<{ projectId: string; cycleId: string }>();
  const search = useSearchParams();
  const icParam = search.get("ic");

  const icsQ = useQuery({
    queryKey: qk.ics(cycleId),
    queryFn: async () => (await getServices()).integration.listByCycle(cycleId),
  });

  const icId = icParam ?? icsQ.data?.find((ic) => ic.status !== "SUPERSEDED")?.id;
  const icQ = useQuery({
    queryKey: ["ic", icId],
    queryFn: async () => (await getServices()).integration.get(icId!),
    enabled: !!icId,
  });

  if (!icQ.data) return <p>Loading integration candidate…</p>;

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Integration Candidate Forge</h1>
      <IcForge ic={icQ.data} projectId={projectId} cycleId={cycleId} />
    </div>
  );
}
